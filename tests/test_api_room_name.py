from datetime import date, time

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.router import router
from src.db.engine import get_db
from src.db.models import Base, Cinema, Movie, Showtime


def test_showtimes_expose_room_name():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    movie = Movie(slug="peli", title="Peli")
    cinema = Cinema(name="Cinépolis Vivo Imperio", city="x")
    db.add_all([movie, cinema])
    db.flush()
    db.add(Showtime(movie_id=movie.id, cinema_id=cinema.id, show_date=date(2026, 11, 14),
                    show_time=time(20, 0), format="2D", room_name="Sala 3"))
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(router)

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    client = TestClient(app)
    for url in ("/api/v1/movies/peli", "/api/v1/movies/peli/showtimes", "/api/v1/showtimes"):
        r = client.get(url)
        assert r.status_code == 200, url
        body = r.json()
        sts = body["showtimes"] if isinstance(body, dict) else body
        assert sts[0]["room_name"] == "Sala 3", url
