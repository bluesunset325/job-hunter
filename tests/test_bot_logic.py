from datetime import datetime, timedelta, timezone

import pytest

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText

import bot
from bot import _handle_status_callback, _send_cards, apply_status, stats_text
from models import Vacancy
from storage import Storage

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


def row(**kw):
    base = dict(id=1, source="hh", url="https://hh.ru/vacancy/1", title="Py", company="A",
                salary_from=None, salary_to=None, currency=None, remote=1, kind="job", score=90,
                why="", red_flags="[]", salary_guess="",
                published_at=(NOW - timedelta(hours=1)).isoformat())
    base.update(kw)
    return base


class FakeMessage:
    def __init__(self):
        self.answers = []

    async def answer(self, text, **kw):
        self.answers.append((text, kw))


@pytest.fixture
def st(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    s.add(Vacancy(source="hh", external_id="1", url="u", title="Py", company="A",
                  published_at=NOW), NOW)
    return s


def test_apply_status(st):
    assert apply_status(st, "st:1:starred") == (1, "starred")
    assert st.get(1)["status"] == "starred"


@pytest.mark.parametrize("bad", ["st:1:deleted", "st:x:starred", "zz", "st:1"])
def test_apply_status_rejects_garbage(st, bad):
    assert apply_status(st, bad) is None
    assert st.get(1)["status"] == "pending"


def test_stats_text(st):
    st.record_failure("kwork")
    st.record_failure("kwork")
    st.set_setting("paused", "1")
    text = stats_text(st, NOW + timedelta(minutes=5))
    assert text.splitlines()[0] == "📊 За 24 ч:"
    assert "hh.ru: собрано 1, прошло фильтр 1, отправлено 0" in text
    assert "❌ Падают: kwork (2 подряд)" in text
    assert "⏸ Рассылка на паузе" in text


async def test_send_cards_empty():
    msg = FakeMessage()
    await _send_cards(msg, [], "Пусто")
    assert msg.answers == [("Пусто", {})]


async def test_send_cards_sleeps_between_and_caps_at_20(monkeypatch):
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(bot.asyncio, "sleep", fake_sleep)
    msg = FakeMessage()
    rows = [row(id=i) for i in range(25)]
    await _send_cards(msg, rows, "empty")
    assert len(msg.answers) == 20
    assert sleeps == [0.5] * 20


class FakeAnswerable:
    def __init__(self, edit_error=None):
        self.answers = []
        self.edits = []
        self.edit_error = edit_error

    async def answer(self, text):
        self.answers.append(text)

    async def edit_text(self, text, **kw):
        if self.edit_error:
            raise self.edit_error
        self.edits.append((text, kw))


async def test_status_callback_rejects_garbage(st):
    fa = FakeAnswerable()
    await _handle_status_callback(st, "zz", fa, fa.answer)
    assert fa.answers == ["?"]
    assert fa.edits == []


async def test_status_callback_answers_then_edits(st):
    fa = FakeAnswerable()
    await _handle_status_callback(st, "st:1:starred", fa, fa.answer)
    assert fa.answers == ["⭐ В избранном"]
    assert len(fa.edits) == 1
    assert "⭐ В избранном" in fa.edits[0][0]


async def test_status_callback_missing_row_does_not_crash(st):
    fa = FakeAnswerable()
    await _handle_status_callback(st, "st:999:starred", fa, fa.answer)
    assert fa.answers == ["⭐ В избранном"]
    assert fa.edits == []


async def test_status_callback_ignores_telegram_bad_request_on_edit(st):
    fa = FakeAnswerable(edit_error=TelegramBadRequest(
        method=EditMessageText(text="x"), message="message is not modified"))
    await _handle_status_callback(st, "st:1:starred", fa, fa.answer)
    assert fa.answers == ["⭐ В избранном"]


def test_setup_logging_configures_root_logger(monkeypatch):
    calls = []
    monkeypatch.setattr(bot.logging, "basicConfig",
                        lambda **kw: calls.append(kw))
    bot.setup_logging()
    assert calls and calls[0]["level"] == bot.logging.INFO
    assert calls[0]["stream"] is bot.sys.stdout
