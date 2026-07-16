from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_OMDB_URL = "http://www.omdbapi.com/"


async def _lookup(client: httpx.AsyncClient, title: str) -> dict:
    resp = await client.get(_OMDB_URL, params={"t": title, "apikey": settings.omdb_api_key})
    return resp.json()


async def find_imdb_rating(title: str, original_title: str | None = None) -> tuple[str | None, str | None]:
    """Look up IMDB rating + URL for a movie title via OMDb API.

    Localized titles (e.g. Spanish release names) often don't match OMDb's
    English entries, so we retry with original_title if the first lookup
    (or its rating) comes up empty.

    Returns:
        (imdb_rating, imdb_url) — both None if not found or lookup fails.
    """
    if not settings.omdb_api_key:
        return None, None

    candidates = [title] + ([original_title] if original_title and original_title != title else [])

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for candidate in candidates:
                data = await _lookup(client, candidate)
                if data.get("Response") == "True":
                    rating = data.get("imdbRating")
                    imdb_id = data.get("imdbID")
                    rating = rating if rating and rating != "N/A" else None
                    imdb_url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None
                    if rating:
                        return rating, imdb_url
                else:
                    logger.info("OMDb: no match for '%s' (%s)", candidate, data.get("Error"))
    except Exception:
        logger.exception("OMDb lookup failed for '%s'", title)
        return None, None

    return None, None
