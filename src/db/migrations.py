from sqlalchemy import inspect, text

from src.db.engine import engine
from src.db.models import Base


def create_tables():
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns():
    inspector = inspect(engine)
    existing_movies = {col["name"] for col in inspector.get_columns("movies")}
    new_movie_columns = {
        "imdb_rating": "VARCHAR",
        "imdb_url": "VARCHAR",
    }
    with engine.begin() as conn:
        for name, sql_type in new_movie_columns.items():
            if name not in existing_movies:
                conn.execute(text(f"ALTER TABLE movies ADD COLUMN {name} {sql_type}"))

        existing_showtimes = {col["name"] for col in inspector.get_columns("showtimes")}
        if "room_name" not in existing_showtimes:
            conn.execute(text("ALTER TABLE showtimes ADD COLUMN room_name VARCHAR"))
