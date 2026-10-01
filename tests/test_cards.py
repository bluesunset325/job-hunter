import json
from datetime import datetime, timedelta, timezone

from cards import card_keyboard, format_card, humanize_age

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


def row(**kw):
    base = dict(id=7, source="hh", url="https://hh.ru/vacancy/1", title="Python-разработчик (боты)",
                company="ООО Ромашка", salary_from=120000, salary_to=160000, currency="RUB",
                remote=1, kind="job", score=82, why="aiogram, парсинг, LLM — прямо твой профиль",
                red_flags='["нужен опыт с Kafka"]', salary_guess="",
                published_at=(NOW - timedelta(hours=2)).isoformat())
    base.update(kw)
    return base


def test_full_card():
    assert format_card(row(), NOW) == (
        "🟢 82 · <b>Python-разработчик (боты)</b> — ООО Ромашка\n"
        "💰 120–160k ₽ · 🌍 удалёнка · hh.ru · 2 ч назад\n"
        "✅ aiogram, парсинг, LLM — прямо твой профиль\n"
        "⚠️ нужен опыт с Kafka")


def test_unscored_freelance_card_escapes_html():
    text = format_card(row(score=None, kind="freelance", title="Бот <script>", company="",
                           salary_from=None, salary_to=1500, why="", red_flags="[]",
                           source="kwork", remote=None), NOW)
    assert text == "⚪ — · 💼<b>Бот &lt;script&gt;</b>\n💰 до 1500 ₽ · 🌍 удалёнка? · Kwork · 2 ч назад"


def test_salary_guess_and_colors():
    t = format_card(row(score=70, salary_from=None, salary_to=None, currency=None,
                        salary_guess="150–200k ₽"), NOW)
    assert t.startswith("🟡 70")
    assert "💰 ~150–200k ₽" in t
    assert format_card(row(score=30), NOW).startswith("🔴 30")


def test_humanize_age():
    assert humanize_age(NOW - timedelta(minutes=10), NOW) == "только что"
    assert humanize_age(NOW - timedelta(hours=5), NOW) == "5 ч назад"
    assert humanize_age(NOW - timedelta(days=3), NOW) == "3 дн назад"


def test_why_and_red_flags_truncated_to_400_chars():
    long_why = "и" * 500
    long_flags = ["ф" * 300, "г" * 300]
    text = format_card(row(why=long_why, red_flags=json.dumps(long_flags)), NOW)
    why_line = next(l for l in text.splitlines() if l.startswith("✅"))
    flags_line = next(l for l in text.splitlines() if l.startswith("⚠️"))
    assert len(why_line) - len("✅ ") <= 400
    assert len(flags_line) - len("⚠️ ") <= 400


def test_keyboard():
    kb = card_keyboard(row())
    buttons = [b for line in kb.inline_keyboard for b in line]
    assert buttons[0].url == "https://hh.ru/vacancy/1"
    assert [b.callback_data for b in buttons[1:]] == ["st:7:starred", "st:7:applied", "st:7:hidden"]
