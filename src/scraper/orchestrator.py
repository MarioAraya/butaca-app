"""Orchestrator: coordinates the scraping pipeline and persists results."""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from datetime import datetime, date

import httpx
from sqlalchemy.orm import Session

from src.config import settings

from src.db.engine import SessionLocal
from src.db.models import Cinema, Movie, ScrapeLog, Showtime, TicketPrice
from src.scraper.cinepolis import fetch_cinepolis
from src.scraper.normandie import fetch_normandie
from src.scraper.omdb import find_imdb_rating
from src.scraper.rate_limiter import RateLimiter
from src.scraper.rooms_html import generate_rooms_html
from src.scraper.youtube import find_trailer

logger = logging.getLogger(__name__)


NORMANDIE_SLUG_PREFIX = "normandie-"
ROOMS_JSON_PATH = "data/cinepolis_rooms.json"
ROOMS_HTML_PATH = "docs/SALAS_CINEPOLIS.html"


def _room_sort_key(room: dict) -> tuple:
    match = re.search(r"\d+", room.get("room_name") or "")
    return (room.get("cinema_name") or "", int(match.group(0)) if match else 999, room.get("room_name") or "")


def load_rooms(json_path: str = ROOMS_JSON_PATH) -> list[dict]:
    """Read the persisted room layouts; empty list if never scraped or unreadable."""
    if not os.path.exists(json_path):
        return []
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        logger.exception("Could not read %s", json_path)
        return []
    return data if isinstance(data, list) else []


def _save_rooms(rooms: list[dict], json_path: str = ROOMS_JSON_PATH, html_path: str = ROOMS_HTML_PATH) -> list[dict]:
    """Merge freshly scraped rooms into the persisted JSON and regenerate the HTML.

    New rooms replace existing ones (keyed by cinema_id + room_name); rooms absent
    from this scrape (failed fetch / no showtime today) keep their last known layout.
    """
    merged: dict[tuple, dict] = {
        (r.get("cinema_id"), r.get("room_name")): r for r in load_rooms(json_path)
    }
    for r in rooms:
        merged[(r.get("cinema_id"), r.get("room_name"))] = r

    result = sorted(merged.values(), key=_room_sort_key)
    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    generate_rooms_html(result, html_path)
    return result


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


def _title_key(title: str | None) -> str:
    """Normalize a title for cross-cinema matching: no accents, punctuation or case."""
    text = unicodedata.normalize("NFKD", title or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _find_canonical_movie(db: Session, title: str) -> Movie | None:
    """Find a movie from a richer source (Cinepolis) with the same normalized title.

    Normandie only provides a title, so when the same film also plays at Cinepolis
    its showtimes are attached to that record (poster, synopsis, rating) instead of
    creating a second, bare `normandie-*` movie.
    """
    key = _title_key(title)
    if not key:
        return None
    candidates = [
        m for m in db.query(Movie).filter(~Movie.slug.startswith(NORMANDIE_SLUG_PREFIX)).all()
        if key in (_title_key(m.title), _title_key(m.original_title))
    ]
    if not candidates:
        return None
    # Prefer the record that is currently in theatres, then the most recently updated
    candidates.sort(key=lambda m: (bool(m.showtimes), m.updated_at or datetime.min), reverse=True)
    return candidates[0]


def _save_showtimes(db: Session, movie: Movie, showtimes_data: list[dict], scope_cinemas: set[str]):
    """Replace the movie's showtimes at `scope_cinemas`, leaving other cinemas untouched.

    A movie can have showtimes from several scrapers, so each one only owns its cinemas.
    """
    scope_ids = [_get_or_create_cinema(db, name).id for name in scope_cinemas]
    if scope_ids:
        db.query(Showtime).filter(
            Showtime.movie_id == movie.id, Showtime.cinema_id.in_(scope_ids)
        ).delete(synchronize_session=False)
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
            room_name=st.get("room_name"),
        ))


def _save_ticket_prices(db: Session, prices_data: list[dict]):
    cinema_names = {p["cinema_name"] for p in prices_data}
    for cinema_name in cinema_names:
        cinema = _get_or_create_cinema(db, cinema_name)
        db.query(TicketPrice).filter(TicketPrice.cinema_id == cinema.id).delete()
    seen: set[tuple] = set()
    for p in prices_data:
        if p.get("price_cents") is None or not p.get("ticket_type_code"):
            continue
        cinema = _get_or_create_cinema(db, p["cinema_name"])
        key = (cinema.id, p.get("format"), p["ticket_type_code"])
        if key in seen:
            continue
        seen.add(key)
        db.add(TicketPrice(
            cinema_id=cinema.id,
            format=p.get("format"),
            ticket_type_code=p["ticket_type_code"],
            description=p.get("description") or p["ticket_type_code"],
            price_cents=p["price_cents"],
            booking_fee_cents=p.get("booking_fee_cents"),
        ))


def _purge_movies_without_showtimes(db: Session) -> int:
    """Delete movies that no longer have any showtime.

    Safe after a partial scrape: a scraper that failed doesn't delete its showtimes,
    so only films that every source has dropped (or whose dates passed) are removed.
    A film that comes back is re-created, with its rating/trailer looked up again.
    """
    stale = db.query(Movie).filter(~Movie.showtimes.any()).all()
    for movie in stale:
        db.delete(movie)
    return len(stale)


async def _send_alert(status: str, errors: list[str], movies_scraped: int, url: str | None = None) -> None:
    """POST a short text summary to ALERT_WEBHOOK_URL. Never raises."""
    url = settings.alert_webhook_url if url is None else url
    if not url:
        return
    lines = [f"Butaca scrape {status}: {movies_scraped} películas guardadas, {len(errors)} errores"]
    lines += [f"- {e[:200]}" for e in errors[:5]]
    if len(errors) > 5:
        lines.append(f"... y {len(errors) - 5} más (GET /api/v1/admin/scrape-logs)")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                url,
                content="\n".join(lines).encode("utf-8"),
                headers={"Title": f"Butaca scrape {status}", "Tags": "warning"},
            )
            r.raise_for_status()
    except Exception:
        logger.exception("Failed to send scrape alert")


async def run_scrape():
    """Execute the scraping pipeline."""
    started_at = datetime.utcnow()
    errors: list[str] = []
    movies_found = 0
    movies_scraped = 0
    imdb_matched = 0
    imdb_attempted = 0

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
            cinepolis_movies, cinepolis_showtimes, cinepolis_prices, cinepolis_rooms = await fetch_cinepolis(rate_limiter)
        except Exception as e:
            cinepolis_movies, cinepolis_showtimes, cinepolis_prices, cinepolis_rooms = [], [], [], []
            errors.append(f"Cinepolis scrape failed: {e}")
            logger.exception("Cinepolis scrape failed")

        movies_found += len(cinepolis_movies)

        if not cinepolis_movies:
            errors.append("No movies returned from Cinepolis")
            logger.error("No Cinepolis movies found, skipping Cinepolis phase")
        else:
            if cinepolis_rooms:
                try:
                    merged_rooms = _save_rooms(cinepolis_rooms)
                    logger.info("Saved %s and %s (%d rooms, %d from this scrape)", ROOMS_JSON_PATH, ROOMS_HTML_PATH, len(merged_rooms), len(cinepolis_rooms))
                except Exception as e:
                    logger.exception("Failed to generate rooms data/html: %s", e)
            showtimes_by_slug: dict[str, list[dict]] = {}
            for st in cinepolis_showtimes:
                showtimes_by_slug.setdefault(st["movie_slug"], []).append(st)
            cinepolis_cinemas = {st["cinema_name"] for st in cinepolis_showtimes}

            for movie_data in cinepolis_movies:
                slug = movie_data["slug"]
                try:
                    if not movie_data.get("trailer_url"):
                        movie_data["trailer_url"] = await find_trailer(movie_data.get("title", slug))

                    imdb_attempted += 1
                    movie_data["imdb_rating"], movie_data["imdb_url"] = await find_imdb_rating(
                        movie_data.get("title", slug), movie_data.get("original_title")
                    )
                    if movie_data["imdb_rating"]:
                        imdb_matched += 1

                    movie = _upsert_movie(db, movie_data)
                    _save_showtimes(db, movie, showtimes_by_slug.get(slug, []), cinepolis_cinemas)
                    db.commit()
                    movies_scraped += 1
                    st_count = len(showtimes_by_slug.get(slug, []))
                    logger.info("Saved: %s (%d showtimes)", slug, st_count)

                except Exception as e:
                    db.rollback()
                    msg = f"Error processing {slug}: {e}"
                    errors.append(msg)
                    logger.exception(msg)

            try:
                _save_ticket_prices(db, cinepolis_prices)
                db.commit()
                logger.info("Saved %d Cinepolis ticket prices", len(cinepolis_prices))
            except Exception as e:
                db.rollback()
                errors.append(f"Error saving ticket prices: {e}")
                logger.exception("Error saving ticket prices")

        # Normandie scrape (no detail phase — title + showtimes only)
        logger.info("=== Normandie scrape ===")
        try:
            norm_movies, norm_showtimes = await fetch_normandie(rate_limiter)
            movies_found += len(norm_movies)

            norm_showtimes_by_slug: dict[str, list[dict]] = {}
            for st in norm_showtimes:
                norm_showtimes_by_slug.setdefault(st["movie_slug"], []).append(st)

            norm_cinemas = {st["cinema_name"] for st in norm_showtimes}

            for movie_data in norm_movies:
                slug = movie_data["slug"]
                try:
                    canonical = _find_canonical_movie(db, movie_data.get("title", ""))
                    if canonical:
                        _save_showtimes(db, canonical, norm_showtimes_by_slug.get(slug, []), norm_cinemas)
                        # Drop the bare duplicate left by scrapes from before the merge
                        db.query(Movie).filter(Movie.slug == slug).delete()
                        db.commit()
                        movies_scraped += 1
                        logger.info("Saved Normandie: %s merged into %s (%d showtimes)",
                                    slug, canonical.slug, len(norm_showtimes_by_slug.get(slug, [])))
                        continue
                    if not movie_data.get("trailer_url"):
                        movie_data["trailer_url"] = await find_trailer(movie_data.get("title", slug))
                    imdb_attempted += 1
                    movie_data["imdb_rating"], movie_data["imdb_url"] = await find_imdb_rating(
                        movie_data.get("title", slug)
                    )
                    if movie_data["imdb_rating"]:
                        imdb_matched += 1
                    movie = _upsert_movie(db, movie_data)
                    _save_showtimes(db, movie, norm_showtimes_by_slug.get(slug, []), norm_cinemas)
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

        try:
            purged = _purge_movies_without_showtimes(db)
            db.commit()
            if purged:
                logger.info("Purged %d movies without showtimes", purged)
        except Exception as e:
            db.rollback()
            errors.append(f"Error purging movies: {e}")
            logger.exception("Error purging movies")

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
        if imdb_attempted:
            log_fn = logger.warning if imdb_matched == 0 else logger.info
            log_fn(
                "IMDb ratings: %d/%d movies matched (check OMDB_API_KEY / quota if this is unexpectedly low — see docs/RUNBOOK.md)",
                imdb_matched, imdb_attempted,
            )
        logger.info(
            "Scrape done: status=%s found=%d scraped=%d errors=%d",
            status, movies_found, movies_scraped, len(errors),
        )
        if status != "success":
            await _send_alert(status, errors, movies_scraped)
