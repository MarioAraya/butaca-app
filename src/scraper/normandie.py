"""Scraper for Cine Arte Normandie (https://normandie.cl/cartelera/).

The cartelera page is a WordPress site with server-rendered HTML.
Structure: div.contenedorcartelera > section.{dayname} > h5 + text nodes + <strong><a>
"""

from __future__ import annotations

import logging
import re
from datetime import date, time, timedelta

import httpx
from bs4 import BeautifulSoup, NavigableString

from src.scraper.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

CINEMA_NAME = "Normandie"
CARTELERA_URL = "https://normandie.cl/cartelera/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return f"normandie-{slug}"


def _parse_time(raw: str) -> time | None:
    match = re.search(r"(\d{1,2}):(\d{2})", raw)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return time(h, m)
    return None


def _parse_week_dates(header_text: str) -> dict[int, date]:
    """
    Parse "Semana desde el jueves 28 de mayo al miércoles 3 de junio"
    into {day_number: date} for all 7 days.
    """
    matches = re.findall(r"(\d+)\s+de\s+(\w+)", header_text.lower())
    if not matches:
        return {}

    start_day = int(matches[0][0])
    start_month = _MONTHS.get(matches[0][1])
    if not start_month:
        return {}

    today = date.today()
    year = today.year
    try:
        start_date = date(year, start_month, start_day)
        # If more than 6 months in the past, it's probably next year
        if (today - start_date).days > 180:
            start_date = date(year + 1, start_month, start_day)
    except ValueError:
        return {}

    return {
        (start_date + timedelta(days=i)).day: start_date + timedelta(days=i)
        for i in range(7)
    }


def _parse_day_section(section) -> list[tuple[time, str]]:
    """Extract (show_time, movie_title) pairs from a day section element."""
    results = []
    current_time = None
    for child in section.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if "hrs" in text.lower():
                t = _parse_time(text)
                if t:
                    current_time = t
        elif child.name == "strong" and current_time is not None:
            title = child.get_text(strip=True)
            if title:
                results.append((current_time, title))
                current_time = None
    return results


def parse_cartelera_html(html: str) -> tuple[list[dict], list[dict]]:
    """Parse the Normandie cartelera HTML into movies and showtimes."""
    soup = BeautifulSoup(html, "html.parser")

    movies: dict[str, dict] = {}
    showtimes: list[dict] = []
    today = date.today()

    for contenedor in soup.find_all("div", class_="contenedorcartelera"):
        titulo_section = contenedor.find("section", class_="titulocartelera")
        if not titulo_section:
            continue

        week_dates = _parse_week_dates(titulo_section.get_text())
        if not week_dates:
            logger.warning("Could not parse week dates from: %s", titulo_section.get_text().strip())
            continue

        for section in contenedor.find_all("section"):
            if "titulocartelera" in section.get("class", []):
                continue

            h5 = section.find("h5")
            if not h5:
                continue

            day_match = re.search(r"(\d+)", h5.get_text())
            if not day_match:
                continue

            show_date = week_dates.get(int(day_match.group(1)))
            if not show_date or show_date < today:
                continue

            for show_time, title in _parse_day_section(section):
                slug = _slugify(title)
                if slug not in movies:
                    movies[slug] = {"slug": slug, "title": title}
                showtimes.append({
                    "movie_slug": slug,
                    "cinema_name": CINEMA_NAME,
                    "show_date": show_date,
                    "show_time": show_time,
                    "language": None,
                    "format": None,
                })

    return list(movies.values()), showtimes


async def fetch_normandie(rate_limiter: RateLimiter) -> tuple[list[dict], list[dict]]:
    """Fetch and parse the Normandie cartelera."""
    await rate_limiter.wait()
    logger.info("Fetching Normandie cartelera: %s", CARTELERA_URL)

    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
        resp = await client.get(CARTELERA_URL)

    if resp.status_code != 200:
        logger.error("Normandie returned HTTP %d", resp.status_code)
        return [], []

    movies, showtimes = parse_cartelera_html(resp.text)
    logger.info("Normandie: %d movies, %d showtimes", len(movies), len(showtimes))
    return movies, showtimes
