"""Phase 1: Extract movies and metadata from the cartelera listing page using Playwright.

The listing page uses Angular.js client-side rendering. After Angular renders,
each movie has a <span data-moviekey="..."> element containing ALL metadata as
data-attributes (titulo, genero, clasificacion, director, actor, distribuidora).

This means we can skip Phase 2 (httpx detail scraper) for metadata — the listing
page already has everything except synopsis, poster URL and trailer.
"""

from __future__ import annotations

import logging
import re

from playwright.async_api import async_playwright

from src.config import settings
from src.scraper.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def _parse_actors(raw: str) -> str | None:
    """Parse actors from a JSON-like string: '["Actor One","Actor Two"]'."""
    if not raw or raw == "Sin datos":
        return raw or None
    actors = re.findall(r'"([^"]+)"', raw)
    return ", ".join(actors) if actors else raw


async def scrape_listing(rate_limiter: RateLimiter) -> list[dict]:
    """Return a list of movie dicts scraped from the cartelera listing page."""
    url = f"{settings.cinepolis_base_url}/cartelera/{settings.scrape_city}/"
    await rate_limiter.wait()

    logger.info("Fetching listing: %s", url)
    movies: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="es-CL",
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)

            # Wait for Angular to inject movie spans (they may not be visible)
            await page.wait_for_selector("[data-moviekey]", state="attached", timeout=30_000)
            await page.wait_for_timeout(2000)  # extra buffer for all movies to render

            elements = await page.query_selector_all("[data-moviekey]")
            seen_slugs: set[str] = set()

            for el in elements:
                slug = await el.get_attribute("data-moviekey")
                if not slug or slug in seen_slugs:
                    continue
                seen_slugs.add(slug)

                title = await el.get_attribute("data-titulo") or ""
                original_title = await el.get_attribute("data-titulooriginal") or ""
                genres = await el.get_attribute("data-genero") or ""
                age_rating = await el.get_attribute("data-clasificacion") or ""
                director = await el.get_attribute("data-director") or ""
                raw_actors = await el.get_attribute("data-actor") or ""
                distributor = await el.get_attribute("data-distribuidora") or ""

                movies.append({
                    "slug": slug,
                    "title": title.strip() or None,
                    "original_title": original_title.strip() or None,
                    "genres": genres.strip() or None,
                    "age_rating": age_rating.strip() or None,
                    "director": director.strip() or None,
                    "actors": _parse_actors(raw_actors.strip()),
                    "distributor": distributor.strip() or None,
                    "detail_url": f"{settings.cinepolis_base_url}/pelicula/{slug}",
                })

        except Exception:
            logger.exception("Error scraping listing page")
        finally:
            await browser.close()

    logger.info("Found %d unique movies", len(movies))
    return movies
