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

import logging
import re
from datetime import date, datetime

from playwright.async_api import async_playwright

from src.scraper.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SITE_URL = "https://cinepolis.com/cl"
GRAPHQL_URL = "https://api-g.cinepolis.com/v2/billboards/graphql"
BILLBOARD_URL = "https://api-g.cinepolis.com/v1/billboards/graphql"
MEDIA_BASE_URL = "https://tickets-static-content.cinepolis.com"

# Cinema slug -> display name. Only cinemas the frontend actually shows
# (see TARGET_PATTERNS in frontend/src/App.jsx: imperio, estaci, normandie).
CINEMAS = {
    "cinepolis-estacion-central-santiago-centro": "Cinépolis Estación Central",
    "cinepolis-vivo-imperio-santiago-centro": "Cinépolis Vivo Imperio",
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
query Billboard($countryId: String!, $cinemaId: String!, $timezone: String!, $isOffSelectorDays: Boolean!) {
  billboardByCinema(countryId: $countryId, cinemaId: $cinemaId, timezone: $timezone, isOffSelectorDays: $isOffSelectorDays) {
    schedules {
      movieId
      dates {
        date
        languages {
          language
          displayLanguage
          showtimes {
            format { name }
            datetime
          }
        }
      }
    }
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
    if result["status"] != 200:
        raise RuntimeError(f"GraphQL {operation_name} failed: HTTP {result['status']} — {result['body'][:200]}")
    import json
    payload = json.loads(result["body"])
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL {operation_name} errors: {payload['errors']}")
    return payload["data"]


async def fetch_cinepolis(rate_limiter: RateLimiter) -> tuple[list[dict], list[dict]]:
    """Fetch movies + showtimes for all configured Cinepolis cinemas."""
    movies: dict[str, dict] = {}
    showtimes: list[dict] = []

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
                            "isOffSelectorDays": True,
                        },
                    )
                except Exception:
                    logger.exception("Failed to fetch billboard for %s", cinema_id)
                    continue

                billboard = board.get("billboardByCinema") or {}
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
                                showtimes.append({
                                    "movie_slug": movie_slug,
                                    "cinema_name": cinema_name,
                                    "show_date": show_date,
                                    "show_time": dt.time(),
                                    "language": language,
                                    "format": (st.get("format") or {}).get("name"),
                                })
        finally:
            await browser.close()

    logger.info("Cinepolis: %d movies, %d showtimes", len(movies), len(showtimes))
    return list(movies.values()), showtimes
