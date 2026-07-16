"""Orchestrator: coordinates the scraping pipeline and persists results."""

from __future__ import annotations

import json
import logging
from datetime import datetime, date

from sqlalchemy.orm import Session

from src.db.engine import SessionLocal
from src.db.models import Cinema, Movie, ScrapeLog, Showtime
from src.scraper.cinepolis import fetch_cinepolis
from src.scraper.normandie import fetch_normandie
from src.scraper.omdb import find_imdb_rating
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

        # Cinepolis: Playwright-driven GraphQL scrape (see src/scraper/cinepolis.py)
        logger.info("=== Cinepolis scrape ===")
        try:
            cinepolis_movies, cinepolis_showtimes = await fetch_cinepolis(rate_limiter)
        except Exception as e:
            cinepolis_movies, cinepolis_showtimes = [], []
            errors.append(f"Cinepolis scrape failed: {e}")
            logger.exception("Cinepolis scrape failed")

        movies_found += len(cinepolis_movies)

        if not cinepolis_movies:
            errors.append("No movies returned from Cinepolis")
            logger.error("No Cinepolis movies found, skipping Cinepolis phase")
        else:
            showtimes_by_slug: dict[str, list[dict]] = {}
            for st in cinepolis_showtimes:
                showtimes_by_slug.setdefault(st["movie_slug"], []).append(st)

            for movie_data in cinepolis_movies:
                slug = movie_data["slug"]
                try:
                    if not movie_data.get("trailer_url"):
                        movie_data["trailer_url"] = await find_trailer(movie_data.get("title", slug))

                    movie_data["imdb_rating"], movie_data["imdb_url"] = await find_imdb_rating(
                        movie_data.get("title", slug), movie_data.get("original_title")
                    )

                    movie = _upsert_movie(db, movie_data)
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

        # Normandie scrape (no detail phase — title + showtimes only)
        logger.info("=== Normandie scrape ===")
        try:
            norm_movies, norm_showtimes = await fetch_normandie(rate_limiter)
            movies_found += len(norm_movies)

            norm_showtimes_by_slug: dict[str, list[dict]] = {}
            for st in norm_showtimes:
                norm_showtimes_by_slug.setdefault(st["movie_slug"], []).append(st)

            for movie_data in norm_movies:
                slug = movie_data["slug"]
                try:
                    if not movie_data.get("trailer_url"):
                        movie_data["trailer_url"] = await find_trailer(movie_data.get("title", slug))
                    movie_data["imdb_rating"], movie_data["imdb_url"] = await find_imdb_rating(
                        movie_data.get("title", slug)
                    )
                    movie = _upsert_movie(db, movie_data)
                    _save_showtimes(db, movie, norm_showtimes_by_slug.get(slug, []))
                    db.commit()
                    movies_scraped += 1
                    logger.info("Saved Normandie: %s (%d showtimes)", slug, len(norm_showtimes_by_slug.get(slug, [])))
                except Exception as e:
                    db.rollback()
                    msg = f"Error processing Normandie {slug}: {e}"
                    errors.append(msg)
                    logger.exception(msg)
        except Exception as e:
            msg = f"Normandie scrape failed: {e}"
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
