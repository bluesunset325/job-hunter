from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.methods import SendMessage

from notifier import TelegramNotifier
from pipeline import PermanentSendError, RetryLater


class FakeBot:
    def __init__(self):
        self.calls = []

    async def send_message(self, chat_id, text, **kw):
        self.calls.append((chat_id, text, kw))
        return SimpleNamespace(message_id=99)


ROW = dict(id=1, source="hh", url="https://hh.ru/vacancy/1", title="Py", company="", salary_from=None,
           salary_to=None, currency=None, remote=1, kind="job", score=90, why="", red_flags="[]",
           salary_guess="", published_at=datetime(2026, 9, 25, tzinfo=timezone.utc).isoformat())


async def test_send_card():
    bot = FakeBot()
    mid = await TelegramNotifier(bot, 123).send_card(ROW)
    assert mid == 99
    chat_id, text, kw = bot.calls[0]
    assert chat_id == 123 and "<b>Py</b>" in text
    assert kw["parse_mode"] == "HTML" and kw["reply_markup"] is not None


async def test_send_text():
    bot = FakeBot()
    await TelegramNotifier(bot, 5).send_text("hi")
    assert bot.calls == [(5, "hi", {})]


def _method():
    return SendMessage(chat_id=1, text="x")


async def test_send_card_translates_retry_after():
    class RetryBot(FakeBot):
        async def send_message(self, chat_id, text, **kw):
            raise TelegramRetryAfter(method=_method(), message="slow down", retry_after=3)

    with pytest.raises(RetryLater) as exc_info:
        await TelegramNotifier(RetryBot(), 123).send_card(ROW)
    assert exc_info.value.seconds == 3


async def test_send_card_translates_bad_request():
    class BadBot(FakeBot):
        async def send_message(self, chat_id, text, **kw):
            raise TelegramBadRequest(method=_method(), message="chat not found")

    with pytest.raises(PermanentSendError):
        await TelegramNotifier(BadBot(), 123).send_card(ROW)
