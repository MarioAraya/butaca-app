"""Phase 2: Extract movie metadata from detail pages using httpx + BeautifulSoup.

Detail pages at /pelicula/{slug} contain server-rendered data-attributes on the
<li id="detail-movie"> element, so no JavaScript rendering is needed.
"""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

from src.config import settings
from src.scraper.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}


def _parse_runtime(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.search(r"(\d+)", raw)
    return int(match.group(1)) if match else None


def parse_detail_html(html: str, slug: str) -> dict | None:
    """Parse movie metadata from a detail page's HTML."""
    soup = BeautifulSoup(html, "html.parser")
    el = soup.find(id="detail-movie")
    if not el:
        logger.warning("No #detail-movie found for slug=%s", slug)
        return None

    # Extract data-attributes
    data = {
        "slug": slug,
        "title": el.get("data-titulo", "").strip() or None,
        "original_title": el.get("data-titulooriginal", "").strip() or None,
        "genres": el.get("data-genero", "").strip() or None,
        "age_rating": el.get("data-clasificacion", "").strip() or None,
        "director": el.get("data-director", "").strip() or None,
        "actors": el.get("data-actor", "").strip() or None,
        "distributor": el.get("data-distribuidora", "").strip() or None,
        "detail_url": f"{settings.cinepolis_base_url}/pelicula/{slug}",
    }

    # Runtime from <span class="duracion">105 min</span>
    duracion_span = soup.find("span", class_="duracion")
    if duracion_span:
        data["runtime_minutes"] = _parse_runtime(duracion_span.get_text())

    # Synopsis: text after <h4>Sinopsis</h4>
    sinopsis_header = soup.find("h4", string=re.compile(r"sinopsis", re.IGNORECASE))
    if sinopsis_header:
        sinopsis_p = sinopsis_header.find_next("p")
        if sinopsis_p:
            data["synopsis"] = sinopsis_p.get_text(strip=True)

    # Poster image — look inside the detail section or nearby
    poster_img = el.find("img")
    if not poster_img:
        # Try the broader movie-detail container
        detail_section = soup.find(class_=re.compile(r"detail|pelicula|movie", re.I))
        if detail_section:
            poster_img = detail_section.find("img")
    if poster_img and poster_img.get("src"):
        src = poster_img["src"]
        if not src.startswith("http"):
            src = f"https:{src}" if src.startswith("//") else f"https://cinepolischile.cl{src}"
        data["poster_url"] = src

    return data


async def scrape_movie_detail(slug: str, rate_limiter: RateLimiter) -> dict | None:
    """Fetch and parse a single movie detail page."""
    url = f"{settings.cinepolis_base_url}/pelicula/{slug}"
    await rate_limiter.wait()

    logger.info("Fetching detail: %s", url)
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            logger.error("HTTP %d for %s", resp.status_code, url)
            return None

    return parse_detail_html(resp.text, slug)
