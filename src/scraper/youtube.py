from __future__ import annotations

import asyncio
import logging
from functools import partial

import yt_dlp

logger = logging.getLogger(__name__)

_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "skip_download": True,
}

_QUERIES = [
    "{title} trailer oficial español",
    "{title} tráiler oficial subtitulado",
    "{title} trailer",
]


def _search_sync(title: str) -> str | None:
    with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
        for tpl in _QUERIES:
            query = tpl.format(title=title)
            try:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                entries = (info or {}).get("entries") or []
                if entries and entries[0].get("id"):
                    url = f"https://www.youtube.com/watch?v={entries[0]['id']}"
                    logger.info("Trailer found for '%s': %s", title, url)
                    return url
            except Exception as e:
                logger.debug("yt-dlp query failed (%s): %s", query, e)
    logger.warning("No trailer found for '%s'", title)
    return None


async def find_trailer(title: str) -> str | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_search_sync, title))
