import json
from pathlib import Path

from src.scraper.cinepolis import parse_seat_layout

FIXTURE = Path(__file__).parent / "fixtures" / "cinepolis_seats_sala3.json"


def _payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["data"]


def test_parse_real_sala3():
    layout = parse_seat_layout(_payload())
    rows = layout["rows"]
    assert len(rows) == 11
    assert rows[0]["name"] == "A" and rows[-1]["name"] == "K"
    assert layout["total_seats"] == 151
    assert [len(r["seats"]) for r in rows] == [16] * 6 + [6, 6, 13, 13, 17]
    a_ids = [s["id"] for s in rows[0]["seats"]]
    assert a_ids[0] == "16" and a_ids[-1] == "1"
    assert layout["aisles_after"] == ["F"]
    assert layout["min_col"] == 0 and layout["max_col"] == 17
    assert layout["seat_image"].endswith("Tradicional.svg")
    assert layout["area_names"] == ["Sala Tradicional"]
    assert {s["status"] for r in rows for s in r["seats"]} <= {"Empty", "Sold"}


def test_parse_empty_payloads():
    for payload in (None, {}, {"seats": None}, {"seats": {"seatLayoutData": None}}):
        layout = parse_seat_layout(payload)
        assert layout["rows"] == [] and layout["total_seats"] == 0
