from __future__ import annotations

import asyncio
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session, joinedload

from src.api.schemas import (
    CinemaOut,
    HealthOut,
    MovieDetail,
    MovieSummary,
    ScrapeLogOut,
    ScrapeResponse,
    ShowtimeOut,
)
from src.api.schemas import TicketPriceOut
from src.config import settings
from src.db.engine import get_db
from src.db.models import Cinema, Movie, ScrapeLog, Showtime, TicketPrice
from src.scraper import orchestrator
from src.scraper.orchestrator import run_scrape

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _require_admin_key(key: str | None = Security(api_key_header)):
    if key != settings.api_admin_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


def _price_lookup(db: Session, cinema_ids: set[int]) -> dict[tuple[int, str | None], list[TicketPriceOut]]:
    if not cinema_ids:
        return {}
    rows = db.query(TicketPrice).filter(TicketPrice.cinema_id.in_(cinema_ids)).all()
    lookup: dict[tuple[int, str | None], list[TicketPriceOut]] = {}
    for row in rows:
        lookup.setdefault((row.cinema_id, row.format), []).append(TicketPriceOut.model_validate(row))
    return lookup


def _showtime_out(st: Showtime, cinema_id: int, cinema_name: str, price_map: dict) -> ShowtimeOut:
    return ShowtimeOut(
        id=st.id,
        cinema_name=cinema_name,
        cinema_id=cinema_id,
        show_date=st.show_date,
        show_time=st.show_time,
        language=st.language,
        format=st.format,
        room_name=st.room_name,
        ticket_prices=price_map.get((cinema_id, st.format), []),
    )


# --- Movies ---


@router.get("/movies", response_model=list[MovieSummary])
def list_movies(
    genre: str | None = Query(None),
    rating: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Movie)
    if genre:
        q = q.filter(Movie.genres.ilike(f"%{genre}%"))
    if rating:
        q = q.filter(Movie.age_rating == rating)
    return q.order_by(Movie.title).all()


def _movie_detail(movie: Movie, price_map: dict) -> MovieDetail:
    showtimes = sorted(movie.showtimes, key=lambda st: (st.show_date, st.show_time))
    return MovieDetail(
        **{c.name: getattr(movie, c.name) for c in Movie.__table__.columns},
        showtimes=[_showtime_out(st, st.cinema_id, st.cinema.name, price_map) for st in showtimes],
    )


@router.get("/billboard", response_model=list[MovieDetail])
def billboard(db: Session = Depends(get_db)):
    """Every movie with upcoming showtimes, showtimes and prices included.

    One request for the whole listing (the frontend used to call /movies and then
    /movies/{slug} for each one).
    """
    movies = (
        db.query(Movie)
        .options(joinedload(Movie.showtimes).joinedload(Showtime.cinema))
        .filter(Movie.showtimes.any(Showtime.show_date >= date.today()))
        .order_by(Movie.title)
        .all()
    )
    price_map = _price_lookup(db, {st.cinema_id for m in movies for st in m.showtimes})
    result = []
    for movie in movies:
        detail = _movie_detail(movie, price_map)
        detail.showtimes = [st for st in detail.showtimes if st.show_date >= date.today()]
        result.append(detail)
    return result


@router.get("/movies/{slug}", response_model=MovieDetail)
def get_movie(slug: str, db: Session = Depends(get_db)):
    movie = (
        db.query(Movie)
        .options(joinedload(Movie.showtimes).joinedload(Showtime.cinema))
        .filter(Movie.slug == slug)
        .first()
    )
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    price_map = _price_lookup(db, {st.cinema_id for st in movie.showtimes})
    return _movie_detail(movie, price_map)


@router.get("/movies/{slug}/showtimes", response_model=list[ShowtimeOut])
def get_movie_showtimes(
    slug: str,
    show_date: date | None = Query(None),
    cinema_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    movie = db.query(Movie).filter(Movie.slug == slug).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    q = (
        db.query(Showtime)
        .join(Cinema)
        .filter(Showtime.movie_id == movie.id)
    )
    if show_date:
        q = q.filter(Showtime.show_date == show_date)
    if cinema_id:
        q = q.filter(Showtime.cinema_id == cinema_id)

    rows = q.order_by(Showtime.show_date, Showtime.show_time).all()
    price_map = _price_lookup(db, {st.cinema_id for st in rows})
    return [_showtime_out(st, st.cinema_id, st.cinema.name, price_map) for st in rows]


# --- Cinemas ---


@router.get("/cinemas", response_model=list[CinemaOut])
def list_cinemas(db: Session = Depends(get_db)):
    return db.query(Cinema).order_by(Cinema.name).all()


@router.get("/cinemas/{cinema_id}/showtimes", response_model=list[ShowtimeOut])
def get_cinema_showtimes(
    cinema_id: int,
    show_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    cinema = db.query(Cinema).filter(Cinema.id == cinema_id).first()
    if not cinema:
        raise HTTPException(status_code=404, detail="Cinema not found")

    q = db.query(Showtime).filter(Showtime.cinema_id == cinema_id)
    if show_date:
        q = q.filter(Showtime.show_date == show_date)

    rows = q.order_by(Showtime.show_date, Showtime.show_time).all()
    price_map = _price_lookup(db, {cinema.id})
    return [_showtime_out(st, cinema.id, cinema.name, price_map) for st in rows]


# --- Showtimes ---


@router.get("/showtimes", response_model=list[ShowtimeOut])
def list_showtimes(
    show_date: date | None = Query(None),
    cinema_id: int | None = Query(None),
    movie_slug: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Showtime).join(Cinema)
    if show_date:
        q = q.filter(Showtime.show_date == show_date)
    if cinema_id:
        q = q.filter(Showtime.cinema_id == cinema_id)
    if movie_slug:
        movie = db.query(Movie).filter(Movie.slug == movie_slug).first()
        if not movie:
            raise HTTPException(status_code=404, detail="Movie not found")
        q = q.filter(Showtime.movie_id == movie.id)

    rows = q.order_by(Showtime.show_date, Showtime.show_time).all()
    price_map = _price_lookup(db, {st.cinema_id for st in rows})
    return [_showtime_out(st, st.cinema_id, st.cinema.name, price_map) for st in rows]


# --- Health ---


def _room_out(room: dict) -> dict:
    """Room topology for clients. Drops per-seat status: it is the occupancy of the
    one session sampled at scrape time, not of whatever showtime the client is viewing."""
    return {
        "cinema_name": room.get("cinema_name"),
        "room_name": room.get("room_name"),
        "formats": room.get("formats") or [],
        "total_seats": room.get("total_seats", 0),
        "min_col": room.get("min_col", 0),
        "max_col": room.get("max_col", 0),
        "aisles_after": room.get("aisles_after") or [],
        "seat_description": room.get("seat_description"),
        "sampled_at": room.get("sampled_at"),
        "rows": [
            {
                "name": row.get("name"),
                "seats": [
                    {"id": s.get("id"), "col": s.get("col"), "style": s.get("style")}
                    for s in row.get("seats") or []
                ],
            }
            for row in room.get("rows") or []
        ],
    }


@router.get("/rooms")
def list_rooms(
    cinema_name: str | None = Query(None, description="Exact cinema name, e.g. 'Cinépolis Vivo Imperio'"),
    room_name: str | None = Query(None, description="Exact room name, e.g. 'Sala 3'"),
):
    """Seat-map topology per room (Cinépolis only), from the last successful scrape."""
    rooms = orchestrator.load_rooms(orchestrator.ROOMS_JSON_PATH)
    if cinema_name:
        rooms = [r for r in rooms if r.get("cinema_name") == cinema_name]
    if room_name:
        rooms = [r for r in rooms if r.get("room_name") == room_name]
    return [_room_out(r) for r in rooms]


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)):
    last_log = db.query(ScrapeLog).order_by(ScrapeLog.id.desc()).first()
    movies_count = db.query(Movie).count()
    return HealthOut(
        status="ok",
        last_scrape_at=last_log.finished_at if last_log else None,
        last_scrape_status=last_log.status if last_log else None,
        movies_count=movies_count,
    )


# --- Admin ---


@router.post("/admin/scrape", response_model=ScrapeResponse, dependencies=[Depends(_require_admin_key)])
async def trigger_scrape():
    asyncio.create_task(run_scrape())
    return ScrapeResponse(message="Scrape started in background")


@router.get("/admin/scrape-logs", response_model=list[ScrapeLogOut], dependencies=[Depends(_require_admin_key)])
def get_scrape_logs(limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    return db.query(ScrapeLog).order_by(ScrapeLog.id.desc()).limit(limit).all()
