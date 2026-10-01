from datetime import datetime, timezone

from sources.telegram import parse_message

D = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
POST = """🔥 **Python-разработчик (aiogram)**

Компания: Ромашка
Формат: удаленно
ЗП: от 150 000 до 200 000 ₽
Нужен опыт с Telegram-ботами и PostgreSQL."""


def test_parse_job_post():
    v = parse_message("pyjobs", 42, POST, D)
    assert v.source == "telegram" and v.external_id == "pyjobs/42"
    assert v.url == "https://t.me/pyjobs/42"
    assert v.title == "Python-разработчик (aiogram)"
    assert v.remote is True and v.kind == "job"
    assert (v.salary_from, v.salary_to, v.currency) == (150000, 200000, "RUB")
    assert v.published_at == D


def test_short_message_ignored():
    assert parse_message("pyjobs", 1, "Всем привет!", D) is None


def test_unknown_remote_and_freelance_tag():
    text = ("#фриланс Нужно написать парсер маркетплейса на Python с выгрузкой в Google Sheets, "
            "бюджет 20 000 руб, срок неделя")
    v = parse_message("fl_chan", 7, text, D)
    assert v.remote is None and v.kind == "freelance"
