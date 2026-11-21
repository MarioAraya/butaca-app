import json
import re
from pathlib import Path

import pytest

from src.scraper.cinepolis import parse_seat_layout
from src.scraper.orchestrator import _save_rooms
from src.scraper.rooms_html import generate_rooms_html

FIXTURE = Path(__file__).parent / "fixtures" / "cinepolis_seats_sala3.json"
CINEMA = "cinepolis-vivo-imperio-santiago-centro"


def _room(name="Sala 3", **extra):
    layout = parse_seat_layout(json.loads(FIXTURE.read_text(encoding="utf-8"))["data"])
    return {
        "cinema_id": CINEMA,
        "cinema_name": "Cinépolis Vivo Imperio",
        "room_name": name,
        "formats": ["2D", "3D"],
        "sampled_session_id": "18424",
        "sampled_at": "2026-11-13T19:00:00",
        **layout,
        **extra,
    }


@pytest.fixture
def rendered(tmp_path):
    out = tmp_path / "salas.html"
    generate_rooms_html([_room()], output_path=str(out))
    return out.read_text(encoding="utf-8")


def test_generate_rooms_html_basics(rendered):
    assert "Cinépolis Vivo Imperio" in rendered
    assert "PANTALLA | SALA 3" in rendered
    assert "Tradicional.svg" in rendered
    assert "151 butacas distribuidas en 11 filas" in rendered
    assert '<span class="badge">2D</span>' in rendered and '<span class="badge">3D</span>' in rendered
    assert "Ocupación muestreada el 2026-11-13T19:00:00" in rendered
    assert "Cinépolis no publica foto de la sala" in rendered
    assert "onclick" not in rendered


def test_rows_order_and_labels(rendered):
    labels = re.findall(r'<div class="row-label">([^<]*)</div>', rendered)
    assert labels[0] == "A"
    assert all(labels)
    assert labels[::2] == list("ABCDEF") + list("GHIJK")


def test_row_a_numbers_descending(rendered):
    row_a = rendered.split('<div class="seat-row">')[1]
    row_a = row_a.split('<div class="seat-row">')[0]
    nums = re.findall(r'<div class="seat (?:available|sold)[^"]*"[^>]*>(\d+)</div>', row_a)
    assert nums == [str(n) for n in range(16, 0, -1)]


def test_seat_count_and_aisle(rendered):
    seats = re.findall(r'<div class="seat (?:available|sold)', rendered)
    assert len(seats) == 151
    assert rendered.count('class="aisle-row"') == 1


def test_save_rooms_merges(tmp_path):
    jp, hp = str(tmp_path / "rooms.json"), str(tmp_path / "rooms.html")
    _save_rooms([_room("Sala 1"), _room("Sala 2")], jp, hp)
    res = _save_rooms([_room("Sala 2", sampled_session_id="999")], jp, hp)
    assert [r["room_name"] for r in res] == ["Sala 1", "Sala 2"]
    saved = json.loads(Path(jp).read_text(encoding="utf-8"))
    assert saved[0]["sampled_session_id"] == "18424"
    assert saved[1]["sampled_session_id"] == "999"
    assert Path(hp).exists()
