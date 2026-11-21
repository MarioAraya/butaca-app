from datetime import date, time, timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.router import router
from src.db.engine import get_db
from src.db.models import Base, Cinema, Movie, Showtime, TicketPrice
from src.scraper import orchestrator

TODAY = date.today()


@pytest.fixture
def Session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed(db):
    cinema = Cinema(name="Cinépolis Vivo Imperio", city="x")
    active = Movie(slug="activa", title="Activa")
    past_only = Movie(slug="pasada", title="Pasada")
    no_shows = Movie(slug="sin-funciones", title="Sin funciones")
    db.add_all([cinema, active, past_only, no_shows])
    db.flush()
    db.add_all([
        Showtime(movie_id=active.id, cinema_id=cinema.id, show_date=TODAY + timedelta(days=1),
                 show_time=time(21, 0), format="2D", room_name="Sala 3"),
        Showtime(movie_id=active.id, cinema_id=cinema.id, show_date=TODAY,
                 show_time=time(18, 0), format="2D", room_name="Sala 1"),
        Showtime(movie_id=active.id, cinema_id=cinema.id, show_date=TODAY - timedelta(days=1),
                 show_time=time(18, 0), format="2D"),
        Showtime(movie_id=past_only.id, cinema_id=cinema.id, show_date=TODAY - timedelta(days=2),
                 show_time=time(18, 0), format="2D"),
        TicketPrice(cinema_id=cinema.id, format="2D", ticket_type_code="0001",
                    description="General", price_cents=540000),
    ])
    db.commit()


def test_billboard_returns_only_upcoming_with_showtimes_and_prices(Session):
    db = Session()
    _seed(db)
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
    body = TestClient(app).get("/api/v1/billboard").json()

    assert [m["slug"] for m in body] == ["activa"]
    sts = body[0]["showtimes"]
    assert [(s["show_date"], s["show_time"]) for s in sts] == [
        (TODAY.isoformat(), "18:00:00"),
        ((TODAY + timedelta(days=1)).isoformat(), "21:00:00"),
    ]
    assert sts[0]["room_name"] == "Sala 1"
    assert sts[0]["ticket_prices"][0]["price_cents"] == 540000


def test_purge_removes_only_movies_without_showtimes(Session):
    db = Session()
    _seed(db)
    assert orchestrator._purge_movies_without_showtimes(db) == 1
    db.commit()
    assert sorted(m.slug for m in db.query(Movie).all()) == ["activa", "pasada"]
    db.close()


@pytest.mark.asyncio
async def test_send_alert_posts_summary(monkeypatch):
    sent = {}

    def handler(request: httpx.Request):
        sent["url"] = str(request.url)
        sent["body"] = request.content.decode()
        sent["title"] = request.headers["Title"]
        return httpx.Response(200)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(orchestrator.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))

    errors = [f"error {i}" for i in range(7)]
    await orchestrator._send_alert("partial", errors, 21, url="https://ntfy.example/topic")

    assert sent["url"] == "https://ntfy.example/topic"
    assert sent["title"] == "Butaca scrape partial"
    assert "21 películas guardadas, 7 errores" in sent["body"]
    assert "- error 4" in sent["body"] and "- error 5" not in sent["body"]
    assert "y 2 más" in sent["body"]


@pytest.mark.asyncio
async def test_send_alert_disabled_and_never_raises(monkeypatch):
    calls = []
    monkeypatch.setattr(orchestrator.httpx, "AsyncClient", lambda **kw: calls.append(kw))
    await orchestrator._send_alert("failed", ["x"], 0, url="")
    assert calls == []

    def boom(request):
        raise httpx.ConnectError("down")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(orchestrator.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(boom), **kw))
    await orchestrator._send_alert("failed", ["x"], 0, url="https://ntfy.example/topic")
