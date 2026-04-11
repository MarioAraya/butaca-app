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
from src.config import settings
from src.db.engine import get_db
from src.db.models import Cinema, Movie, ScrapeLog, Showtime
from src.scraper.orchestrator import run_scrape

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _require_admin_key(key: str | None = Security(api_key_header)):
    if key != settings.api_admin_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


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

    showtimes = [
        ShowtimeOut(
            id=st.id,
            cinema_name=st.cinema.name,
            cinema_id=st.cinema_id,
            show_date=st.show_date,
            show_time=st.show_time,
            language=st.language,
            format=st.format,
        )
        for st in movie.showtimes
    ]
    return MovieDetail(
        **{c.name: getattr(movie, c.name) for c in Movie.__table__.columns},
        showtimes=showtimes,
    )


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
    return [
        ShowtimeOut(
            id=st.id,
            cinema_name=st.cinema.name,
            cinema_id=st.cinema_id,
            show_date=st.show_date,
            show_time=st.show_time,
            language=st.language,
            format=st.format,
        )
        for st in rows
    ]


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
    return [
        ShowtimeOut(
            id=st.id,
            cinema_name=cinema.name,
            cinema_id=cinema.id,
            show_date=st.show_date,
            show_time=st.show_time,
            language=st.language,
            format=st.format,
        )
        for st in rows
    ]


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
    return [
        ShowtimeOut(
            id=st.id,
            cinema_name=st.cinema.name,
            cinema_id=st.cinema_id,
            show_date=st.show_date,
            show_time=st.show_time,
            language=st.language,
            format=st.format,
        )
        for st in rows
    ]


# --- Health ---


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
