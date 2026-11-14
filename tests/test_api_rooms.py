import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.router import router
from src.scraper import orchestrator
from src.scraper.cinepolis import parse_seat_layout

FIXTURE = Path(__file__).parent / "fixtures" / "cinepolis_seats_sala3.json"


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _room(cinema, name):
    layout = parse_seat_layout(json.loads(FIXTURE.read_text(encoding="utf-8"))["data"])
    return {"cinema_id": cinema, "cinema_name": cinema, "room_name": name, "formats": ["2D"],
            "sampled_session_id": "1", "sampled_at": "2026-11-13T19:00:00", **layout}


def test_rooms_empty_when_never_scraped(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator, "ROOMS_JSON_PATH", str(tmp_path / "missing.json"))
    r = _client().get("/api/v1/rooms")
    assert r.status_code == 200
    assert r.json() == []


def test_rooms_filter_and_shape(tmp_path, monkeypatch):
    path = tmp_path / "rooms.json"
    path.write_text(json.dumps([_room("Cine A", "Sala 1"), _room("Cine A", "Sala 3"), _room("Cine B", "Sala 3")]),
                    encoding="utf-8")
    monkeypatch.setattr(orchestrator, "ROOMS_JSON_PATH", str(path))
    client = _client()

    assert len(client.get("/api/v1/rooms").json()) == 3
    assert len(client.get("/api/v1/rooms", params={"cinema_name": "Cine A"}).json()) == 2

    rooms = client.get("/api/v1/rooms", params={"cinema_name": "Cine B", "room_name": "Sala 3"}).json()
    assert len(rooms) == 1
    room = rooms[0]
    assert room["total_seats"] == 151
    assert room["rows"][0]["name"] == "A"
    assert [s["id"] for s in room["rows"][0]["seats"]][:2] == ["16", "15"]
    # Stale occupancy and internal ids must not leak to clients
    assert "status" not in room["rows"][0]["seats"][0]
    assert "sampled_session_id" not in room


def test_rooms_corrupt_file_returns_empty(tmp_path, monkeypatch):
    path = tmp_path / "rooms.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(orchestrator, "ROOMS_JSON_PATH", str(path))
    assert _client().get("/api/v1/rooms").json() == []
