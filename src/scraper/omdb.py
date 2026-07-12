from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_OMDB_URL = "http://www.omdbapi.com/"


async def find_imdb_rating(title: str) -> tuple[str | None, str | None]:
    """Look up IMDB rating + URL for a movie title via OMDb API.

    Returns:
        (imdb_rating, imdb_url) — both None if not found or lookup fails.
    """
    if not settings.omdb_api_key:
        return None, None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_OMDB_URL, params={"t": title, "apikey": settings.omdb_api_key})
        data = resp.json()
    except Exception:
        logger.exception("OMDb lookup failed for '%s'", title)
        return None, None

    if data.get("Response") != "True":
        logger.info("OMDb: no match for '%s' (%s)", title, data.get("Error"))
        return None, None

    rating = data.get("imdbRating")
    imdb_id = data.get("imdbID")
    rating = rating if rating and rating != "N/A" else None
    imdb_url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None
    return rating, imdb_url
