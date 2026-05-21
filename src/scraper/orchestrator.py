"""Orchestrator: coordinates the scraping pipeline and persists results.

Flow:
  Phase 1 (API call):   GetNowPlayingByCity → all movies + showtimes in one JSON request
  Phase 2 (httpx+BS4):  Detail page per movie → synopsis + genres (not in API)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date

from sqlalchemy.orm import Session

from src.db.engine import SessionLocal
from src.db.models import Cinema, Movie, ScrapeLog, Showtime
from src.scraper.api_client import fetch_now_playing
from src.scraper.detail import scrape_movie_detail
from src.scraper.rate_limiter import RateLimiter
from src.scraper.youtube import find_trailer

logger = logging.getLogger(__name__)


def _upsert_movie(db: Session, data: dict) -> Movie:
    movie = db.query(Movie).filter(Movie.slug == data["slug"]).first()
    valid_cols = {c.name for c in Movie.__table__.columns}
    clean = {k: v for k, v in data.items() if k in valid_cols}
    if movie:
        for key, value in clean.items():
            if value is not None:
                setattr(movie, key, value)
        movie.updated_at = datetime.utcnow()
    else:
        movie = Movie(**clean)
        db.add(movie)
    db.flush()
    return movie


def _get_or_create_cinema(db: Session, name: str) -> Cinema:
    cinema = db.query(Cinema).filter(Cinema.name == name).first()
    if not cinema:
        cinema = Cinema(name=name, city=name.lower().replace(" ", "-"))
        db.add(cinema)
        db.flush()
    return cinema


def _save_showtimes(db: Session, movie: Movie, showtimes_data: list[dict]):
    db.query(Showtime).filter(Showtime.movie_id == movie.id).delete()
    seen: set[tuple] = set()
    for st in showtimes_data:
        cinema = _get_or_create_cinema(db, st["cinema_name"])
        key = (movie.id, cinema.id, st["show_date"], st["show_time"], st.get("language"), st.get("format"))
        if key in seen:
            continue
        seen.add(key)
        db.add(Showtime(
            movie_id=movie.id,
            cinema_id=cinema.id,
            show_date=st["show_date"],
            show_time=st["show_time"],
            language=st.get("language"),
            format=st.get("format"),
        ))


async def run_scrape():
    """Execute the scraping pipeline."""
    started_at = datetime.utcnow()
    errors: list[str] = []
    movies_found = 0
    movies_scraped = 0

    rate_limiter = RateLimiter()
    db = SessionLocal()

    try:
        # Purge stale showtimes from past dates
        deleted = db.query(Showtime).filter(Showtime.show_date < date.today()).delete()
        db.commit()
        if deleted:
            logger.info("Purged %d past showtimes", deleted)

        # Phase 1: Get all movies + showtimes from the JSON API (1 HTTP request)
        logger.info("=== Phase 1: Fetching from API ===")
        api_movies, all_showtimes = await fetch_now_playing(rate_limiter)
        movies_found = len(api_movies)

        if not api_movies:
            errors.append("No movies returned from API")
            logger.error("No movies found, aborting")
            return

        # Build showtime lookup: slug → list of showtime dicts
        showtimes_by_slug: dict[str, list[dict]] = {}
        for st in all_showtimes:
            showtimes_by_slug.setdefault(st["movie_slug"], []).append(st)

        # Phase 2: Enrich each movie with synopsis + genres from detail page
        for movie_data in api_movies:
            slug = movie_data["slug"]
            try:
                logger.info("=== Phase 2: Detail for %s ===", slug)
                detail = await scrape_movie_detail(slug, rate_limiter)

                merged = {**movie_data}
                if detail:
                    # Only take fields the API doesn't provide well
                    for field in ("synopsis", "genres"):
                        if detail.get(field):
                            merged[field] = detail[field]
                    # Prefer API poster/trailer if detail has better version
                    if not merged.get("poster_url") and detail.get("poster_url"):
                        merged["poster_url"] = detail["poster_url"]

                if not merged.get("trailer_url"):
                    merged["trailer_url"] = await find_trailer(merged.get("title", slug))

                movie = _upsert_movie(db, merged)
                _save_showtimes(db, movie, showtimes_by_slug.get(slug, []))
                db.commit()
                movies_scraped += 1
                st_count = len(showtimes_by_slug.get(slug, []))
                logger.info("Saved: %s (%d showtimes)", slug, st_count)

            except Exception as e:
                db.rollback()
                msg = f"Error processing {slug}: {e}"
                errors.append(msg)
                logger.exception(msg)

    finally:
        status = "success" if not errors else ("partial" if movies_scraped > 0 else "failed")
        db.add(ScrapeLog(
            started_at=started_at,
            finished_at=datetime.utcnow(),
            status=status,
            movies_found=movies_found,
            movies_scraped=movies_scraped,
            errors=json.dumps(errors) if errors else None,
        ))
        db.commit()
        db.close()
        logger.info(
            "Scrape done: status=%s found=%d scraped=%d errors=%d",
            status, movies_found, movies_scraped, len(errors),
        )
