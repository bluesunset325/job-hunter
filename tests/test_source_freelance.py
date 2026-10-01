from datetime import datetime, timezone
from pathlib import Path

from sources.freelance import FlSource, KworkSource


def text(name):
    return Path(f"tests/fixtures/{name}").read_text(encoding="utf-8")


def test_kwork():
    items = KworkSource.parse(text("kwork.html"))
    assert len(items) == 2
    v = items[0]
    assert v.source == "kwork" and v.external_id == "3259017"
    assert v.url == "https://kwork.ru/projects/3259017"
    assert v.title == "Доработка/Перенос асинхронного автобая на Python с бот"
    assert v.kind == "freelance" and v.remote is True
    assert (v.salary_to, v.currency) == (1500, "RUB")
    assert v.published_at == datetime(2026, 9, 25, 10, 55, 12, tzinfo=timezone.utc)  # 13:55 МСК
    assert "&laquo;" not in v.description and "«" in v.description


def test_kwork_without_state_returns_empty():
    assert KworkSource.parse("<html></html>") == []


def test_fl():
    items = FlSource.parse(text("fl.rss"))
    assert len(items) == 2
    v = items[0]
    assert v.source == "fl" and v.external_id == "5523345"
    assert v.title == "Помощь в настройке ИИ Qwen 3.8 27B на компьютер или мощнее"
    assert v.kind == "freelance" and v.remote is True
    assert v.published_at == datetime(2026, 9, 25, 10, 50, 24, tzinfo=timezone.utc)
    assert "Прикладное программирование" in v.description
