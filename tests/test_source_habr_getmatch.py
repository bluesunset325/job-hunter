import json
from datetime import datetime, timezone
from pathlib import Path

from sources.getmatch import GetMatchSource
from sources.habr_career import HabrCareerSource


def load(name):
    return json.loads(Path(f"tests/fixtures/{name}").read_text(encoding="utf-8"))


def test_parse_habr():
    items = HabrCareerSource.parse(load("habr_career.json"))
    assert len(items) == 2
    a, b = items
    assert a.source == "habr_career" and a.external_id == "1000168585"
    assert a.url == "https://career.habr.com/vacancies/1000168585"
    assert a.title == "Инженер по тестированию (Python / API) / QA Engineer"
    assert a.company == "IBS"
    assert a.remote is True
    assert a.salary_from is None and a.currency is None
    assert a.published_at == datetime(2026, 9, 21, 7, 42, 44, tzinfo=timezone.utc)
    assert "Python" in a.description
    assert b.title == "Python разработчик"
    assert "FastAPI" in b.description


def test_parse_habr_salary_currency_mapping():
    data = load("habr_career.json")
    data["list"][0]["salary"] = {"from": 150000, "to": 250000, "currency": "rur"}
    v = HabrCareerSource.parse(data)[0]
    assert (v.salary_from, v.salary_to, v.currency) == (150000, 250000, "RUB")


def test_parse_getmatch():
    items = GetMatchSource.parse(load("getmatch.json"))
    assert len(items) == 2
    a, b = items
    assert a.source == "getmatch" and a.external_id == "35469"
    assert a.url == "https://getmatch.ru/vacancies/35469-data-analyst-offsite-search-optimisation"
    assert a.title == "Data Analyst: Offsite Search Optimisation"
    assert a.company == "Constructor.io"
    assert a.remote is True
    assert (a.salary_from, a.salary_to, a.currency) == (7500, 10000, "USD")
    assert a.published_at == datetime(2026, 9, 25, 9, 1, 12, 674780, tzinfo=timezone.utc)
    assert b.company == "Сбер"
    assert b.remote is False
    assert b.salary_from is None
    assert "<b>" not in b.description
