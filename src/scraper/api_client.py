"""Direct client for the Cinepolis internal JSON API.

The Angular frontend calls these ASP.NET endpoints. We replicate those calls
with httpx to get all movie + showtime data without needing a browser.
"""

from __future__ import annotations

import logging
import re
from datetime import date, time

import httpx

from src.config import settings
from src.scraper.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://cinepolischile.cl/cartelera/santiago-centro/",
}

# Spanish month names used in the API's ShowtimeDate field
_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _parse_showtime_date(raw: str) -> date | None:
    """Parse '31 marzo' or '01 abril' into a date object (current year)."""
    raw = raw.strip().lower()
    match = re.match(r"(\d{1,2})\s+(\w+)", raw)
    if not match:
        return None
    day = int(match.group(1))
    month = _MONTHS.get(match.group(2))
    if not month:
        return None
    year = date.today().year
    # Handle year rollover (e.g. December → January next year)
    today = date.today()
    try:
        d = date(year, month, day)
        if d < today and (today.month - month) > 6:
            d = date(year + 1, month, day)
        return d
    except ValueError:
        return None


def _parse_time(raw: str) -> time | None:
    """Parse '13:10' into a time object."""
    match = re.match(r"(\d{1,2}):(\d{2})", raw.strip())
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return time(h, m)
    return None


def _parse_runtime(raw: str | None) -> int | None:
    """Parse '105 min' into 105."""
    if not raw:
        return None
    match = re.search(r"(\d+)", raw)
    return int(match.group(1)) if match else None


def _extract_movies_and_showtimes(api_data: dict) -> tuple[list[dict], list[dict]]:
    """
    Parse the GetNowPlayingByCity response into movies and showtimes.

    Returns:
        movies: list of movie dicts (unique by slug)
        showtimes: list of showtime dicts with cinema_name, movie_slug, date, time, language, format
    """
    movies: dict[str, dict] = {}  # slug → movie data
    cinemas: dict[str, dict] = {}  # key → cinema data
    showtimes: list[dict] = []

    for cinema_entry in api_data.get("Cinemas", []):
        cinema_key = cinema_entry.get("Key", "")
        cinema_name = cinema_entry.get("Name", "")
        cinema_id = cinema_entry.get("Id")

        if cinema_key and cinema_name:
            cinemas[cinema_key] = {
                "key": cinema_key,
                "name": cinema_name,
                "id": cinema_id,
            }

        for date_entry in cinema_entry.get("Dates", []):
            raw_date = date_entry.get("ShowtimeDate", "")
            show_date = _parse_showtime_date(raw_date)
            if not show_date:
                continue

            for movie in date_entry.get("Movies", []):
                slug = movie.get("Key", "")
                if not slug:
                    continue

                # Collect unique movie metadata
                if slug not in movies:
                    actors_raw = movie.get("Actors") or []
                    actors = ", ".join(a for a in actors_raw if a and a.strip()) or None

                    movies[slug] = {
                        "slug": slug,
                        "title": movie.get("Title") or None,
                        "original_title": movie.get("OriginalTitle") or None,
                        "age_rating": movie.get("Rating") or None,
                        "runtime_minutes": _parse_runtime(movie.get("RunTime")),
                        "director": movie.get("Director") or None,
                        "actors": actors,
                        "distributor": movie.get("Distributor") or None,
                        "poster_url": movie.get("Poster") or None,
                        "trailer_url": movie.get("Trailer") or None,
                        "cinepolis_id": str(movie.get("Id", "")),
                        "detail_url": f"{settings.cinepolis_base_url}/pelicula/{slug}",
                    }

                # Collect showtimes
                for fmt in movie.get("Formats", []):
                    language = fmt.get("Name") or fmt.get("Language") or "ESP"
                    fmt_name = "3D" if "3D" in (fmt.get("VistaId") or "") else "2D"
                    if fmt.get("IsExperience"):
                        fmt_name = fmt.get("VistaId", fmt_name)

                    for st in fmt.get("Showtimes", []):
                        show_time = _parse_time(st.get("Time", ""))
                        if not show_time:
                            continue
                        showtimes.append({
                            "movie_slug": slug,
                            "cinema_name": cinema_name,
                            "show_date": show_date,
                            "show_time": show_time,
                            "language": language,
                            "format": fmt_name,
                        })

    return list(movies.values()), showtimes


async def fetch_now_playing(
    rate_limiter: RateLimiter,
    city: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Fetch all movies and showtimes from the Cinepolis API.

    Returns:
        (movies, showtimes) — movies is unique per slug, showtimes has one entry per screening.
    """
    city = city or settings.scrape_city
    await rate_limiter.wait()

    logger.info("Calling GetNowPlayingByCity for city=%s", city)
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
        resp = await client.post(
            f"{settings.cinepolis_base_url}/Cartelera.aspx/GetNowPlayingByCity",
            json={"claveCiudad": city, "esVIP": False},
        )

    if resp.status_code != 200:
        logger.error("API returned HTTP %d", resp.status_code)
        return [], []

    try:
        data = resp.json()
        api_data = data.get("d", {})
    except Exception:
        logger.exception("Failed to parse API response")
        return [], []

    movies, showtimes = _extract_movies_and_showtimes(api_data)
    logger.info("API returned %d movies, %d showtimes", len(movies), len(showtimes))
    return movies, showtimes
