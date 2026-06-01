"""Tests for the Normandie cartelera scraper."""

from datetime import date, time
from unittest.mock import patch

import pytest

from src.scraper.normandie import (
    _parse_time,
    _parse_week_dates,
    _slugify,
    parse_cartelera_html,
)

# Minimal HTML that mirrors the real Normandie structure
SAMPLE_HTML = """
<html><body>
<div class="contenedorcartelera">
  <section class="titulocartelera">
    <h4>Semana desde el jueves 5 de junio al miércoles 11 de junio</h4>
  </section>
  <section class="jueves">
    <h5>Jueves 5</h5>
    <hr/>
    15:00 hrs.<br/>
    <strong><a href="https://www.flow.cl/btn.php?token=abc">Submarine</a></strong>
    <hr/>
    19:15 hrs.<br/>
    <strong><a href="https://www.flow.cl/btn.php?token=def">Obsesión</a></strong>
  </section>
  <section class="viernes">
    <h5>Viernes 6</h5>
    <hr/>
    17:00 hrs.<br/>
    <strong><a href="https://www.flow.cl/btn.php?token=ghi">El faro</a></strong>
  </section>
</div>
</body></html>
"""

CROSS_MONTH_HTML = """
<html><body>
<div class="contenedorcartelera">
  <section class="titulocartelera">
    <h4>Semana desde el jueves 29 de mayo al miércoles 4 de junio</h4>
  </section>
  <section class="martes">
    <h5>Martes 3</h5>
    <hr/>
    18:00 hrs.<br/>
    <strong><a href="https://www.flow.cl/btn.php?token=xyz">Casablanca</a></strong>
  </section>
  <section class="miercoles">
    <h5>Miércoles 4</h5>
    <hr/>
    20:00 hrs.<br/>
    <strong><a href="https://www.flow.cl/btn.php?token=uvw">Whiplash</a></strong>
  </section>
</div>
</body></html>
"""


class TestParseTime:
    def test_standard_time(self):
        assert _parse_time("15:00 hrs.") == time(15, 0)

    def test_time_with_whitespace(self):
        assert _parse_time("  17:30 hrs. ") == time(17, 30)

    def test_no_time(self):
        assert _parse_time("sin hora") is None

    def test_invalid_hours(self):
        assert _parse_time("25:00") is None


class TestSlugify:
    def test_simple(self):
        assert _slugify("Submarine") == "normandie-submarine"

    def test_special_chars(self):
        assert _slugify("Obsesión") == "normandie-obsesión"

    def test_spaces(self):
        assert _slugify("El faro") == "normandie-el-faro"

    def test_multiple_spaces(self):
        assert _slugify("Stop  making  sense") == "normandie-stop-making-sense"


class TestParseWeekDates:
    def test_same_month(self):
        with patch("src.scraper.normandie.date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 5)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = _parse_week_dates("Semana desde el jueves 5 de junio al miércoles 11 de junio")
        assert result[5] == date(2026, 6, 5)
        assert result[11] == date(2026, 6, 11)
        assert len(result) == 7

    def test_cross_month(self):
        with patch("src.scraper.normandie.date") as mock_date:
            mock_date.today.return_value = date(2026, 5, 29)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = _parse_week_dates("Semana desde el jueves 29 de mayo al miércoles 4 de junio")
        assert result[29] == date(2026, 5, 29)
        assert result[4] == date(2026, 6, 4)
        assert len(result) == 7

    def test_unparseable(self):
        result = _parse_week_dates("sin fechas aquí")
        assert result == {}


class TestParseCarshowHTML:
    def test_extracts_movies(self):
        with patch("src.scraper.normandie.date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            movies, showtimes = parse_cartelera_html(SAMPLE_HTML)

        titles = {m["title"] for m in movies}
        assert "Submarine" in titles
        assert "Obsesión" in titles
        assert "El faro" in titles

    def test_slugs_prefixed(self):
        with patch("src.scraper.normandie.date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            movies, _ = parse_cartelera_html(SAMPLE_HTML)

        for m in movies:
            assert m["slug"].startswith("normandie-")

    def test_showtimes_dates_and_times(self):
        with patch("src.scraper.normandie.date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            _, showtimes = parse_cartelera_html(SAMPLE_HTML)

        submarine_sts = [s for s in showtimes if "submarine" in s["movie_slug"]]
        assert len(submarine_sts) == 1
        assert submarine_sts[0]["show_date"] == date(2026, 6, 5)
        assert submarine_sts[0]["show_time"] == time(15, 0)
        assert submarine_sts[0]["cinema_name"] == "Normandie"

    def test_past_dates_excluded(self):
        with patch("src.scraper.normandie.date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 7)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            _, showtimes = parse_cartelera_html(SAMPLE_HTML)

        # June 5 and 6 are in the past relative to June 7
        assert all(s["show_date"] >= date(2026, 6, 7) for s in showtimes)

    def test_cross_month_dates(self):
        with patch("src.scraper.normandie.date") as mock_date:
            mock_date.today.return_value = date(2026, 5, 29)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            movies, showtimes = parse_cartelera_html(CROSS_MONTH_HTML)

        casablanca_sts = [s for s in showtimes if "casablanca" in s["movie_slug"]]
        assert casablanca_sts[0]["show_date"] == date(2026, 6, 3)

        whiplash_sts = [s for s in showtimes if "whiplash" in s["movie_slug"]]
        assert whiplash_sts[0]["show_date"] == date(2026, 6, 4)

    def test_no_duplicates(self):
        with patch("src.scraper.normandie.date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            movies, _ = parse_cartelera_html(SAMPLE_HTML)

        slugs = [m["slug"] for m in movies]
        assert len(slugs) == len(set(slugs))
