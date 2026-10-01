import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message
from dotenv import load_dotenv

from cards import SOURCE_TITLES, card_keyboard, format_card
from config import load_config
from storage import Storage

STATUS_LABELS = {"starred": "⭐ В избранном", "applied": "✅ Отклик отправлен", "hidden": "🙈 Скрыто"}
HELP = ("Команды:\n/top — лучшие за сутки\n/starred — избранное\n/all — ниже порога\n"
        "/stats — статистика\n/pause, /resume — пауза рассылки")
BOT_SEND_DELAY = 0.5
MAX_CARDS_PER_MESSAGE = 20


def apply_status(storage: Storage, callback_data: str) -> tuple[int, str] | None:
    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "st" or not parts[1].isdigit() or parts[2] not in STATUS_LABELS:
        return None
    id_, status = int(parts[1]), parts[2]
    storage.set_status(id_, status)
    return id_, status


def stats_text(storage: Storage, now: datetime) -> str:
    lines = ["📊 За 24 ч:"]
    for source, s in storage.stats(now - timedelta(hours=24)).items():
        lines.append(f"{SOURCE_TITLES.get(source, source)}: собрано {s['collected']}, "
                     f"прошло фильтр {s['passed']}, отправлено {s['sent']}")
    failing = [(n, storage.source_state(n).consecutive_failures) for n in SOURCE_TITLES]
    failing = [f"{n} ({c} подряд)" for n, c in failing if c > 0]
    if failing:
        lines.append("❌ Падают: " + ", ".join(failing))
    if storage.get_setting("paused", "0") == "1":
        lines.append("⏸ Рассылка на паузе")
    return "\n".join(lines)


async def _send_cards(message: Message, rows, empty: str) -> None:
    if not rows:
        await message.answer(empty)
        return
    now = datetime.now(timezone.utc)
    for r in rows[:MAX_CARDS_PER_MESSAGE]:
        await message.answer(format_card(r, now), parse_mode="HTML", reply_markup=card_keyboard(r),
                             link_preview_options=LinkPreviewOptions(is_disabled=True))
        await asyncio.sleep(BOT_SEND_DELAY)


async def _handle_status_callback(storage: Storage, data: str, message, answer) -> None:
    res = apply_status(storage, data)
    if not res:
        await answer("?")
        return
    id_, status = res
    label = STATUS_LABELS[status]
    await answer(label)
    row = storage.get(id_)
    if row is None:
        return
    try:
        await message.edit_text(
            format_card(row, datetime.now(timezone.utc)) + "\n\n" + label, parse_mode="HTML",
            reply_markup=None if status == "hidden" else card_keyboard(row),
            link_preview_options=LinkPreviewOptions(is_disabled=True))
    except TelegramBadRequest:
        pass


def build_dispatcher(storage: Storage, chat_id: int, threshold: int) -> Dispatcher:
    dp = Dispatcher()
    mine = F.chat.id == chat_id

    @dp.message(Command("start"), mine)
    async def start(m: Message):
        await m.answer(HELP)

    @dp.message(Command("top"), mine)
    async def top(m: Message):
        await _send_cards(m, storage.top(datetime.now(timezone.utc) - timedelta(hours=24), 10),
                          "За сутки ничего нового")

    @dp.message(Command("starred"), mine)
    async def starred(m: Message):
        await _send_cards(m, storage.starred(), "Избранное пусто")

    @dp.message(Command("all"), mine)
    async def all_(m: Message):
        await _send_cards(m, storage.below_threshold(threshold, 20), "Пусто")

    @dp.message(Command("stats"), mine)
    async def stats(m: Message):
        await m.answer(stats_text(storage, datetime.now(timezone.utc)))

    @dp.message(Command("pause"), mine)
    async def pause(m: Message):
        storage.set_setting("paused", "1")
        await m.answer("⏸ Рассылка на паузе")

    @dp.message(Command("resume"), mine)
    async def resume(m: Message):
        storage.set_setting("paused", "0")
        await m.answer("▶️ Рассылка включена")

    @dp.callback_query(F.data.startswith("st:"), F.message.chat.id == chat_id)
    async def on_status(c: CallbackQuery):
        await _handle_status_callback(storage, c.data, c.message, c.answer)

    return dp


async def amain() -> None:
    cfg = load_config("config.yaml")
    storage = Storage(cfg.db_path)
    bot = Bot(os.environ[cfg.telegram.bot_token_env])
    dp = build_dispatcher(storage, cfg.telegram.chat_id, cfg.scoring.score_threshold)
    await dp.start_polling(bot)


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    os.chdir(Path(__file__).resolve().parent)
    load_dotenv()
    setup_logging()
    asyncio.run(amain())


if __name__ == "__main__":
    main()
