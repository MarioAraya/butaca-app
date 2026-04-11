"""Phase 3: Extract showtimes and trailer URL from movie detail pages using Playwright.

Showtimes and the YouTube trailer are rendered client-side by Angular,
so we need Playwright to wait for the DOM to populate.
"""

from __future__ import annotations

import logging
import re
from datetime import date, time

from playwright.async_api import Page, async_playwright

from src.config import settings
from src.scraper.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def _parse_time(raw: str) -> time | None:
    """Parse a time string like '13:10' or '1:10 PM' into a time object."""
    raw = raw.strip()
    match = re.match(r"(\d{1,2}):(\d{2})", raw)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return time(h, m)
    return None


async def _extract_trailer(page: Page) -> str | None:
    """Extract YouTube trailer URL from an iframe or link on the page."""
    # Try iframe first
    iframe = await page.query_selector('iframe[src*="youtube"]')
    if iframe:
        src = await iframe.get_attribute("src")
        if src:
            return src

    # Try a direct YouTube link
    yt_link = await page.query_selector('a[href*="youtube.com/watch"]')
    if yt_link:
        return await yt_link.get_attribute("href")

    return None


async def _extract_showtimes(page: Page) -> list[dict]:
    """Extract showtimes grouped by cinema from the rendered page."""
    showtimes: list[dict] = []
    today = date.today()

    # The page renders cinema sections with showtimes
    # Look for cinema name headers and their associated times
    cinema_sections = await page.query_selector_all(".showtimesCinema, .contenedorHorarioCinema, [ng-repeat*='cinema']")

    if not cinema_sections:
        # Fallback: try to find any showtime structure
        cinema_sections = await page.query_selector_all(".row.horarios, .cinema-showtimes")

    if not cinema_sections:
        # Last resort: parse the full page text for patterns
        logger.warning("No cinema sections found via selectors, trying text-based extraction")
        return await _extract_showtimes_from_text(page, today)

    for section in cinema_sections:
        # Cinema name
        name_el = await section.query_selector("h3, h4, .cinema-name, .nombreCinema")
        cinema_name = ""
        if name_el:
            cinema_name = (await name_el.inner_text()).strip()

        if not cinema_name:
            # Try getting text from first heading-like element
            text = await section.inner_text()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            cinema_name = lines[0] if lines else "Desconocido"

        # Language blocks
        lang_blocks = await section.query_selector_all(".language-block, .idiomaHorario, [ng-repeat*='lang']")
        if lang_blocks:
            for lb in lang_blocks:
                lang_el = await lb.query_selector(".language-name, .idioma")
                language = (await lang_el.inner_text()).strip() if lang_el else "ESP"

                time_els = await lb.query_selector_all(".showtime-btn, .horario-btn, button, a.btn")
                for te in time_els:
                    raw = (await te.inner_text()).strip()
                    t = _parse_time(raw)
                    if t:
                        showtimes.append({
                            "cinema_name": cinema_name,
                            "show_date": today,
                            "show_time": t,
                            "language": language,
                            "format": "2D",
                        })
        else:
            # No language blocks, grab all time-like buttons
            time_els = await section.query_selector_all("button, a.btn, .showtime, .horario")
            for te in time_els:
                raw = (await te.inner_text()).strip()
                t = _parse_time(raw)
                if t:
                    showtimes.append({
                        "cinema_name": cinema_name,
                        "show_date": today,
                        "show_time": t,
                        "language": "ESP",
                        "format": "2D",
                    })

    return showtimes


async def _extract_showtimes_from_text(page: Page, today: date) -> list[dict]:
    """Fallback text-based extraction when CSS selectors don't match."""
    showtimes: list[dict] = []
    content = await page.inner_text("body")
    lines = content.split("\n")

    current_cinema = None
    current_language = "ESP"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect cinema names (typically contain "Cinépolis" or known patterns)
        if "cinépolis" in line.lower() or "cinepolis" in line.lower():
            current_cinema = line
            continue

        # Detect language lines
        if line in ("ESP", "SUB", "DOB", "SUBT", "ESPA"):
            current_language = line
            continue

        # Detect time patterns
        times_found = re.findall(r"\b(\d{1,2}:\d{2})\b", line)
        for raw_t in times_found:
            t = _parse_time(raw_t)
            if t and current_cinema:
                showtimes.append({
                    "cinema_name": current_cinema,
                    "show_date": today,
                    "show_time": t,
                    "language": current_language,
                    "format": "2D",
                })

    return showtimes


async def scrape_showtimes(slug: str, rate_limiter: RateLimiter) -> dict:
    """Scrape showtimes and trailer for a movie. Returns {trailer_url, showtimes}."""
    url = f"{settings.cinepolis_base_url}/pelicula/{slug}"
    await rate_limiter.wait()

    logger.info("Fetching showtimes: %s", url)
    result: dict = {"trailer_url": None, "showtimes": []}

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
            # Give Angular a moment to render showtimes
            await page.wait_for_timeout(5000)

            result["trailer_url"] = await _extract_trailer(page)
            result["showtimes"] = await _extract_showtimes(page)

            logger.info(
                "slug=%s trailer=%s showtimes=%d",
                slug,
                bool(result["trailer_url"]),
                len(result["showtimes"]),
            )
        except Exception:
            logger.exception("Error scraping showtimes for %s", slug)
        finally:
            await browser.close()

    return result
