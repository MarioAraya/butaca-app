from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel


class ShowtimeOut(BaseModel):
    id: int
    cinema_name: str
    cinema_id: int
    show_date: date
    show_time: time
    language: str | None
    format: str | None

    model_config = {"from_attributes": True}


class MovieSummary(BaseModel):
    id: int
    slug: str
    title: str
    genres: str | None
    age_rating: str | None
    runtime_minutes: int | None
    poster_url: str | None
    detail_url: str | None

    model_config = {"from_attributes": True}


class MovieDetail(MovieSummary):
    original_title: str | None
    synopsis: str | None
    director: str | None
    actors: str | None
    distributor: str | None
    trailer_url: str | None
    created_at: datetime | None
    updated_at: datetime | None
    showtimes: list[ShowtimeOut] = []


class CinemaOut(BaseModel):
    id: int
    name: str
    city: str | None

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    last_scrape_at: datetime | None
    last_scrape_status: str | None
    movies_count: int


class ScrapeLogOut(BaseModel):
    id: int
    started_at: datetime | None
    finished_at: datetime | None
    status: str | None
    movies_found: int | None
    movies_scraped: int | None

    model_config = {"from_attributes": True}


class ScrapeResponse(BaseModel):
    message: str
