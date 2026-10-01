import argparse
import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from httpclient import Http
from models import Vacancy
from sources.base import Source
from textutil import parse_salary

_LEADING_JUNK = re.compile(r"^[\W_]+", re.UNICODE)
_FREELANCE = ("#фриланс", "#проект", "#freelance", "заказ")


def parse_message(channel: str, msg_id: int, text: str, date: datetime) -> Vacancy | None:
    if not text or len(text) < 80:
        return None
    first = next(line for line in text.splitlines() if line.strip())
    title = _LEADING_JUNK.sub("", first.replace("*", "").replace("_", "").replace("#", "")).strip()
    low = text.lower()
    s_from, s_to, cur = parse_salary(text)
    return Vacancy(
        source="telegram", external_id=f"{channel}/{msg_id}", url=f"https://t.me/{channel}/{msg_id}",
        title=title[:120], company="", published_at=date.astimezone(timezone.utc),
        kind="freelance" if any(t in low for t in _FREELANCE) else "job",
        remote=True if ("удален" in low or "удалён" in low or "remote" in low) else None,
        salary_from=s_from, salary_to=s_to, currency=cur, description=text[:4000])


class TelegramSource(Source):
    name = "telegram"

    def __init__(self, cfg, api_id: int, api_hash: str):
        self.cfg = cfg
        self.api_id = api_id
        self.api_hash = api_hash

    async def fetch(self, http: Http) -> list[Vacancy]:
        from telethon import TelegramClient

        if not Path(self.cfg.session_path + ".session").exists():
            raise RuntimeError("run: python -m sources.telegram --login")
        out = []
        async with TelegramClient(self.cfg.session_path, self.api_id, self.api_hash) as client:
            for channel in self.cfg.channels:
                async for m in client.iter_messages(channel, limit=50):
                    v = parse_message(channel, m.id, m.raw_text or "", m.date)
                    if v:
                        out.append(v)
        return out


def _login() -> None:
    from dotenv import load_dotenv
    from telethon import TelegramClient

    from config import load_config

    load_dotenv()
    cfg = load_config("config.yaml").telethon
    Path(cfg.session_path).parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(cfg.session_path, int(os.environ[cfg.api_id_env]),
                            os.environ[cfg.api_hash_env])
    client.start()  # спросит телефон и код в терминале
    print("OK, session saved:", cfg.session_path + ".session")
    client.disconnect()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--login", action="store_true")
    if p.parse_args().login:
        _login()
