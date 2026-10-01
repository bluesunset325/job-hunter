from datetime import datetime, timezone

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import LinkPreviewOptions

from cards import card_keyboard, format_card
from pipeline import PermanentSendError, RetryLater


class TelegramNotifier:
    def __init__(self, bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id

    async def send_card(self, row) -> int:
        try:
            msg = await self.bot.send_message(
                self.chat_id, format_card(row, datetime.now(timezone.utc)), parse_mode="HTML",
                reply_markup=card_keyboard(row),
                link_preview_options=LinkPreviewOptions(is_disabled=True))
        except TelegramRetryAfter as e:
            raise RetryLater(e.retry_after) from e
        except TelegramBadRequest as e:
            raise PermanentSendError(str(e)) from e
        return msg.message_id

    async def send_text(self, text: str) -> None:
        await self.bot.send_message(self.chat_id, text)
