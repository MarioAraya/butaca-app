from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import Base, Movie, Showtime
from src.scraper.orchestrator import _find_canonical_movie, _save_showtimes, _title_key

DAY = date(2026, 11, 14)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _st(cinema, hour):
    return {"cinema_name": cinema, "show_date": DAY, "show_time": time(hour, 0), "language": None, "format": None}


@pytest.mark.parametrize("a,b", [
    ("Caballo Salvaje Nueve", "Caballo salvaje nueve"),
    ("WILDWOOD EL BOSQUE SALVAJE", "Wildwood: El bosque salvaje"),
    ("Ebenezer: Los Fantasmas de Navidad", "Ebenezer: Los fantasmas de Navidad"),
    ("Cómo robar un banco", "Como robar un banco "),
])
def test_title_key_matches_variants(a, b):
    assert _title_key(a) == _title_key(b)


def test_title_key_keeps_different_titles_apart():
    assert _title_key("JU-ON: EL GRITO") != _title_key("JU-ON: EL GRITO la maldición")
    assert _title_key(None) == ""


def test_find_canonical_matches_title_or_original_title(db):
    db.add_all([
        Movie(slug="yo-soy-rocky", title="Yo soy Rocky", original_title="I Play Rocky"),
        Movie(slug="normandie-your-name", title="Your Name"),
    ])
    db.flush()
    assert _find_canonical_movie(db, "YO SOY ROCKY").slug == "yo-soy-rocky"
    assert _find_canonical_movie(db, "I play Rocky").slug == "yo-soy-rocky"
    # A normandie-only record is never a merge target, and unknown titles don't match
    assert _find_canonical_movie(db, "Your Name") is None
    assert _find_canonical_movie(db, "De Palma") is None
    assert _find_canonical_movie(db, "") is None


def test_save_showtimes_only_replaces_scoped_cinemas(db):
    movie = Movie(slug="yo-soy-rocky", title="Yo soy Rocky")
    db.add(movie)
    db.flush()
    _save_showtimes(db, movie, [_st("Cinépolis Vivo Imperio", 18), _st("Cinépolis Vivo Imperio", 21)],
                    {"Cinépolis Vivo Imperio"})
    _save_showtimes(db, movie, [_st("Normandie", 19)], {"Normandie"})
    db.flush()
    assert db.query(Showtime).count() == 3

    # Re-scraping Normandie replaces only its own showtimes
    _save_showtimes(db, movie, [_st("Normandie", 16)], {"Normandie"})
    db.flush()
    rows = sorted((s.cinema.name, s.show_time.hour) for s in db.query(Showtime).all())
    assert rows == [("Cinépolis Vivo Imperio", 18), ("Cinépolis Vivo Imperio", 21), ("Normandie", 16)]

    # A scraper that no longer lists the movie at its cinemas clears them
    _save_showtimes(db, movie, [], {"Cinépolis Vivo Imperio"})
    db.flush()
    assert [s.cinema.name for s in db.query(Showtime).all()] == ["Normandie"]
