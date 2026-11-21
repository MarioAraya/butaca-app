"""Scraper for the new Cinepolis Chile site (https://cinepolis.com/cl).

Cinepolis migrated from cinepolischile.cl (plain ASP.NET JSON API) to a
Next.js micro-frontend platform. The billboard/movies data lives behind a
GraphQL API (api-g.cinepolis.com) protected by Cloudflare bot management —
plain httpx requests get a 403 challenge page regardless of headers, so we
drive a real headless browser (Playwright) to pass the challenge, then issue
the GraphQL queries via `fetch()` inside the page (reusing its cleared
session/cookies).

The GraphQL API already returns synopsis, genre, rating and poster inline,
so unlike the old two-phase pipeline (listing + detail-page scrape) this is
a single phase per cinema.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime

from playwright.async_api import async_playwright

from src.scraper.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SITE_URL = "https://cinepolis.com/cl"
GRAPHQL_URL = "https://api-g.cinepolis.com/v2/billboards/graphql"
BILLBOARD_URL = "https://api-g.cinepolis.com/v2/billboards/graphql"
TICKETS_URL = "https://api-g.cinepolis.com/v1/ticket/graphql"
MEDIA_BASE_URL = "https://tickets-static-content.cinepolis.com"

# Cloudflare occasionally blocks a single scrape attempt (seen so far only on
# the unattended 06:00 cron run, never on manual triggers minutes apart) — a
# fresh browser session/navigation is usually enough to get past it, so retry
# the whole session rather than just the failing request.
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 30

# Cinema slug -> display name. Only cinemas the frontend actually shows
# (see TARGET_PATTERNS in frontend/src/App.jsx: imperio, estaci, normandie).
CINEMAS = {
    "cinepolis-estacion-central-santiago-centro": "Cinépolis Estación Central",
    "cinepolis-vivo-imperio-santiago-centro": "Cinépolis Vivo Imperio",
}

# Vista (booking system) cinema IDs, required by the Tickets GraphQL query.
# Static — fetched once via shared-services/locations/graphql Cinemas query,
# doesn't change unless Cinepolis re-provisions the cinema in Vista.
CINEMA_VISTA_IDS = {
    "cinepolis-estacion-central-santiago-centro": "712",
    "cinepolis-vivo-imperio-santiago-centro": "916",
}

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Public client-side key the frontend sends on every GraphQL call — not a secret,
# just required for the API to accept the request (401 without it).
_API_KEY = "lQM6Mkvri1iHksKKCfpAiwGXq0YUZA7Nn6XAXRPr4i13LwXo"

_MOVIES_QUERY = """
query Movies($countryId: String!, $category: String, $cinemas: String, $after: String, $limit: Int) {
  movies(countryId: $countryId, category: $category, cinemas: $cinemas, after: $after, limit: $limit) {
    edges {
      node {
        id
        name
        originalName
        distributor
        rating
        genre
        synopsis
        length
        media { resource type code sizes { large medium small } }
      }
    }
  }
}
"""

_BILLBOARD_QUERY = """
query Billboard($countryId: String!, $cinemaId: String!, $timezone: String!, $isAbsoluteExperiencePath: Boolean) {
  billboardByCinema(
    countryId: $countryId
    cinemaId: $cinemaId
    timezone: $timezone
    isAbsoluteExperiencePath: $isAbsoluteExperiencePath
  ) {
    dates
    schedules {
      cinemaId
      cityId
      movieId
      dates {
        date
        languages {
          language
          displayLanguage
          showtimes {
            format {
              icon
              name
              __typename
            }
            sessionId
            datetime
            screen
            experience {
              icon
              name
              __typename
            }
            movieVistaId
            cinemaVistaId
            alerts {
              section
              title
              message
              __typename
            }
            availability
            isAllocatedSeating
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

_SEATS_QUERY = """
query Seats($countryId: String!, $sessionId: String!, $cinemaVistaId: String!, $userSessionId: String, $experience: String) {
  seats(
    countryId: $countryId
    sessionId: $sessionId
    cinemaVistaId: $cinemaVistaId
    userSessionId: $userSessionId
    experience: $experience
  ) {
    maxQuantity
    seatLayoutData {
      areas {
        rowCount
        columnCount
        description
        areaCategoryCode
        rows {
          physicalName
          seats {
            id
            status
            originalStatus
            seatStyle
            position {
              columnIndex
              rowIndex
              areaNumber
              __typename
            }
            __typename
          }
          __typename
        }
        __typename
      }
      areaCategories {
        areaCategoryCode
        seatType
        capacity
        name
        description
        image
        hopk
        selectedSeats {
          areaNumber
          rowIndex
          columnIndex
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

_TICKETS_QUERY = """
query Tickets($countryId: String!, $sessionId: String!, $cinemaVistaId: String!) {
  tickets(countryId: $countryId, cinemaVistaId: $cinemaVistaId, sessionId: $sessionId) {
    areaCategoryCode
    tickets {
      ticketTypeCode
      description
      priceInCents
      bookingFee
      __typename
    }
    __typename
  }
}
"""


def _parse_runtime(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.search(r"(\d+)", raw)
    return int(match.group(1)) if match else None


def _poster_url(media: list[dict]) -> str | None:
    for entry in media:
        if entry.get("code") == "poster":
            path = (entry.get("sizes") or {}).get("large")
            resource = entry.get("resource")
            if path and resource:
                return f"{MEDIA_BASE_URL}{path}{resource}"
    return None


async def _graphql(page, url: str, operation_name: str, query: str, variables: dict) -> dict:
    result = await page.evaluate(
        """
        async ({url, operationName, query, variables, apiKey}) => {
          const resp = await fetch(url, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'x-apikey': apiKey,
              'country-id': 'CL',
              'language': 'ES'
            },
            body: JSON.stringify({operationName, query, variables})
          });
          return {status: resp.status, body: await resp.text()};
        }
        """,
        {"url": url, "operationName": operation_name, "query": query, "variables": variables, "apiKey": _API_KEY},
    )
    if result["status"] == 401:
        logger.error(
            "Cinepolis GraphQL %s: 401 Unauthorized — x-apikey likely rotated. "
            "See docs/RUNBOOK.md to extract the new key from the site's network requests.",
            operation_name,
        )
        raise RuntimeError(f"GraphQL {operation_name}: 401 Unauthorized (stale x-apikey?)")
    if result["status"] == 403:
        logger.error(
            "Cinepolis GraphQL %s: 403 — likely a Cloudflare bot-management block. "
            "See docs/RUNBOOK.md.",
            operation_name,
        )
        raise RuntimeError(f"GraphQL {operation_name}: 403 (Cloudflare block?)")
    if result["status"] != 200:
        raise RuntimeError(f"GraphQL {operation_name} failed: HTTP {result['status']} — {result['body'][:200]}")
    import json
    payload = json.loads(result["body"])
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL {operation_name} errors: {payload['errors']}")
    return payload["data"]


def parse_seat_layout(seats_payload: dict | None) -> dict:
    """Normalize a `Seats` GraphQL response (the `data` dict) into a room topology.

    The API returns rows back-to-front (rowIndex 0 = farthest from the screen)
    and columnIndex ascending, while the site draws row A next to the screen
    and columns descending left-to-right. Rows are returned screen -> back,
    seats in display order (col descending), empty rows dropped.
    """
    layout = ((seats_payload or {}).get("seats") or {}).get("seatLayoutData") or {}
    areas = layout.get("areas") or []
    cats = layout.get("areaCategories") or []

    rows: list[dict] = []
    for area in areas:
        for r in (area or {}).get("rows") or []:
            raw_seats = (r or {}).get("seats") or []
            if not raw_seats:
                continue
            seats = []
            for s in raw_seats:
                pos = s.get("position") or {}
                seats.append({
                    "id": str(s.get("id") or ""),
                    "col": pos.get("columnIndex") or 0,
                    "row_index": (pos.get("rowIndex") or 0),
                    "status": s.get("status") or "Empty",
                    "style": s.get("seatStyle") or "Normal",
                })
            row_index = seats[0]["row_index"]
            for s in seats:
                del s["row_index"]
            seats.sort(key=lambda s: s["col"], reverse=True)
            rows.append({"name": r.get("physicalName") or "", "row_index": row_index, "seats": seats})

    rows.sort(key=lambda r: r["row_index"], reverse=True)
    aisles_after = [
        cur["name"] for cur, nxt in zip(rows, rows[1:])
        if cur["row_index"] - nxt["row_index"] > 1
    ]
    cols = [s["col"] for r in rows for s in r["seats"]]
    first_cat = cats[0] if cats and cats[0] else {}
    return {
        "rows": rows,
        "aisles_after": aisles_after,
        "min_col": min(cols) if cols else 0,
        "max_col": max(cols) if cols else 0,
        "total_seats": len(cols),
        "seat_image": first_cat.get("image"),
        "seat_description": first_cat.get("description"),
        "area_names": [a.get("description") for a in areas if a and a.get("description")],
    }


async def fetch_cinepolis(rate_limiter: RateLimiter) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Fetch movies + showtimes + ticket prices + room seat maps for all configured Cinepolis cinemas."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            movies, showtimes, prices, rooms = await _fetch_cinepolis_once(rate_limiter)
        except Exception as e:
            last_error = e
            logger.warning("Cinepolis scrape attempt %d/%d failed: %s", attempt, MAX_ATTEMPTS, e)
        else:
            if movies:
                if attempt > 1:
                    logger.info("Cinepolis scrape succeeded on attempt %d/%d", attempt, MAX_ATTEMPTS)
                return movies, showtimes, prices, rooms
            last_error = None
            logger.warning("Cinepolis scrape attempt %d/%d returned 0 movies", attempt, MAX_ATTEMPTS)

        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)

    logger.error(
        "Cinepolis scrape failed after %d attempts%s — see docs/RUNBOOK.md",
        MAX_ATTEMPTS, f": {last_error}" if last_error else " (kept returning 0 movies)",
    )
    return [], [], [], []


async def _fetch_cinepolis_once(rate_limiter: RateLimiter) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Single attempt: launch a browser, pass Cloudflare, fetch all cinemas."""
    movies: dict[str, dict] = {}
    showtimes: list[dict] = []
    prices: list[dict] = []
    rooms: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(user_agent=_USER_AGENT)
            await page.goto(SITE_URL, wait_until="networkidle", timeout=60000)

            for cinema_id, cinema_name in CINEMAS.items():
                await rate_limiter.wait()
                logger.info("Fetching Cinepolis movies for %s", cinema_id)
                try:
                    data = await _graphql(
                        page, GRAPHQL_URL, "Movies", _MOVIES_QUERY,
                        {"countryId": "CL", "category": "now-playing", "cinemas": cinema_id, "limit": 100},
                    )
                except Exception:
                    logger.exception("Failed to fetch movies for %s", cinema_id)
                    continue

                for edge in data["movies"]["edges"]:
                    node = edge["node"]
                    slug = node["id"]
                    if slug not in movies:
                        movies[slug] = {
                            "slug": slug,
                            "title": node.get("name"),
                            "original_title": node.get("originalName"),
                            "age_rating": node.get("rating"),
                            "runtime_minutes": _parse_runtime(node.get("length")),
                            "distributor": node.get("distributor"),
                            "genres": ", ".join(node.get("genre") or []) or None,
                            "synopsis": node.get("synopsis"),
                            "poster_url": _poster_url(node.get("media") or []),
                            "cinepolis_id": slug,
                            "detail_url": f"{SITE_URL}/pelicula/{slug}",
                        }

                await rate_limiter.wait()
                logger.info("Fetching Cinepolis billboard for %s", cinema_id)
                try:
                    board = await _graphql(
                        page, BILLBOARD_URL, "Billboard", _BILLBOARD_QUERY,
                        {
                            "countryId": "CL",
                            "cinemaId": cinema_id,
                            "timezone": "America/Santiago",
                            "isAbsoluteExperiencePath": True,
                        },
                    )
                except Exception:
                    logger.exception("Failed to fetch billboard for %s", cinema_id)
                    continue

                billboard = board.get("billboardByCinema") or {}
                sample_session_by_format: dict[str, str] = {}
                sample_session_by_room: dict[str, dict] = {}

                for schedule in billboard.get("schedules", []):
                    movie_slug = schedule["movieId"]
                    for date_entry in schedule.get("dates", []):
                        try:
                            show_date = date.fromisoformat(date_entry["date"])
                        except ValueError:
                            continue
                        for lang in date_entry.get("languages", []):
                            language = lang.get("displayLanguage") or lang.get("language")
                            for st in lang.get("showtimes", []):
                                try:
                                    dt = datetime.fromisoformat(st["datetime"])
                                except (ValueError, TypeError):
                                    continue
                                format_name = (st.get("format") or {}).get("name")
                                screen_val = st.get("screen")
                                room_name = f"Sala {screen_val}" if screen_val else None

                                showtimes.append({
                                    "movie_slug": movie_slug,
                                    "cinema_name": cinema_name,
                                    "show_date": show_date,
                                    "show_time": dt.time(),
                                    "language": language,
                                    "format": format_name,
                                    "room_name": room_name,
                                })
                                session_id = st.get("sessionId")
                                if session_id and format_name not in sample_session_by_format:
                                    sample_session_by_format[format_name] = session_id
                                if session_id and room_name:
                                    info = sample_session_by_room.setdefault(room_name, {
                                        "session_id": session_id,
                                        "format": format_name,
                                        "experience": (st.get("experience") or {}).get("name"),
                                        "formats": [],
                                    })
                                    if format_name and format_name not in info["formats"]:
                                        info["formats"].append(format_name)

                vista_id = CINEMA_VISTA_IDS.get(cinema_id)

                # Fetch room seat layouts
                for room_name, sess_info in sorted(sample_session_by_room.items()):
                    await rate_limiter.wait()
                    experience = (sess_info.get("experience") or "TRADICIONAL").upper()
                    logger.info(
                        "Fetching Cinepolis seat layout for %s / %s (session %s, experience %s)",
                        cinema_name, room_name, sess_info["session_id"], experience,
                    )
                    try:
                        seats_data = await _graphql(
                            page, TICKETS_URL, "Seats", _SEATS_QUERY,
                            {
                                "countryId": "CL",
                                "sessionId": sess_info["session_id"],
                                "cinemaVistaId": vista_id,
                                "experience": experience,
                            },
                        )
                        layout = parse_seat_layout(seats_data)
                        if layout["total_seats"] == 0:
                            logger.warning("Empty seat layout for %s / %s, skipping", cinema_name, room_name)
                            continue
                        rooms.append({
                            "cinema_id": cinema_id,
                            "cinema_name": cinema_name,
                            "room_name": room_name,
                            "formats": sess_info["formats"],
                            "sampled_session_id": sess_info["session_id"],
                            "sampled_at": datetime.now().isoformat(timespec="seconds"),
                            "experience": experience,
                            **layout,
                        })
                    except Exception:
                        logger.exception("Failed to fetch seat layout for %s / %s", cinema_name, room_name)
                        continue

                # Fetch ticket prices
                for format_name, session_id in sample_session_by_format.items():
                    await rate_limiter.wait()
                    logger.info("Fetching Cinepolis ticket prices for %s / %s", cinema_id, format_name)
                    try:
                        ticket_data = await _graphql(
                            page, TICKETS_URL, "Tickets", _TICKETS_QUERY,
                            {"countryId": "CL", "sessionId": session_id, "cinemaVistaId": vista_id},
                        )
                    except Exception:
                        logger.exception("Failed to fetch ticket prices for %s / %s", cinema_id, format_name)
                        continue
                    for area in ticket_data.get("tickets") or []:
                        for ticket in area.get("tickets") or []:
                            prices.append({
                                "cinema_name": cinema_name,
                                "format": format_name,
                                "ticket_type_code": ticket.get("ticketTypeCode"),
                                "description": ticket.get("description"),
                                "price_cents": ticket.get("priceInCents"),
                                "booking_fee_cents": ticket.get("bookingFee"),
                            })
        finally:
            await browser.close()

    logger.info("Cinepolis: %d movies, %d showtimes, %d prices, %d rooms", len(movies), len(showtimes), len(prices), len(rooms))
    return list(movies.values()), showtimes, prices, rooms
