from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    original_title = Column(String)
    synopsis = Column(Text)
    genres = Column(String)
    age_rating = Column(String)
    runtime_minutes = Column(Integer)
    director = Column(String)
    actors = Column(String)
    distributor = Column(String)
    poster_url = Column(String)
    trailer_url = Column(String)
    detail_url = Column(String)
    cinepolis_id = Column(String)
    imdb_rating = Column(String)
    imdb_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    showtimes = relationship("Showtime", back_populates="movie", cascade="all, delete-orphan")


class Cinema(Base):
    __tablename__ = "cinemas"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    city = Column(String, default="santiago-centro")

    showtimes = relationship("Showtime", back_populates="cinema")


class Showtime(Base):
    __tablename__ = "showtimes"
    __table_args__ = (
        UniqueConstraint("movie_id", "cinema_id", "show_date", "show_time", "language", "format"),
    )

    id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    cinema_id = Column(Integer, ForeignKey("cinemas.id"), nullable=False)
    show_date = Column(Date, nullable=False)
    show_time = Column(Time, nullable=False)
    language = Column(String)
    format = Column(String)
    room_name = Column(String, nullable=True)

    movie = relationship("Movie", back_populates="showtimes")
    cinema = relationship("Cinema", back_populates="showtimes")


class TicketPrice(Base):
    __tablename__ = "ticket_prices"
    __table_args__ = (
        UniqueConstraint("cinema_id", "format", "ticket_type_code"),
    )

    id = Column(Integer, primary_key=True)
    cinema_id = Column(Integer, ForeignKey("cinemas.id"), nullable=False)
    format = Column(String)
    ticket_type_code = Column(String, nullable=False)
    description = Column(String, nullable=False)
    price_cents = Column(Integer, nullable=False)
    booking_fee_cents = Column(Integer)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cinema = relationship("Cinema")


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    status = Column(String)
    movies_found = Column(Integer, default=0)
    movies_scraped = Column(Integer, default=0)
    errors = Column(Text)
