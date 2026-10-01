import asyncio
import fcntl
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

import aiohttp
from aiogram import Bot
from dotenv import load_dotenv

from config import load_config
from httpclient import Http
from notifier import TelegramNotifier
from pipeline import run
from scorer import Scorer
from sources import build_sources
from storage import Storage

ROOT = Path(__file__).resolve().parent
PLACEHOLDER_TOKEN = "123456:ABC..."


def check_setup(cfg, env) -> list[str]:
    problems = []
    token = env.get(cfg.telegram.bot_token_env, "").strip()
    if not token or token == PLACEHOLDER_TOKEN or ":" not in token:
        problems.append(f"{cfg.telegram.bot_token_env} в .env не задан: впиши токен от @BotFather")
    if not cfg.telegram.chat_id:
        problems.append("telegram.chat_id в config.yaml равен 0: впиши свой chat_id от @userinfobot")
    return problems


def setup_logging(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler(sys.stdout)],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def amain() -> None:
    cfg = load_config("config.yaml")
    storage = Storage(cfg.db_path)
    scorer = Scorer(cfg.ollama.url, cfg.ollama.model, cfg.ollama.timeout_s,
                    Path(cfg.resume_path).read_text(encoding="utf-8"),
                    notes=cfg.candidate_notes)
    bot = Bot(os.environ[cfg.telegram.bot_token_env])
    try:
        async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20, sock_connect=10)) as session:
            rep = await run(build_sources(cfg), Http(session), storage, scorer,
                            TelegramNotifier(bot, cfg.telegram.chat_id), cfg,
                            datetime.now(timezone.utc))
        logging.getLogger("job_hunter").info("run done: %s", rep)
    except Exception:
        logging.getLogger("job_hunter").exception("run failed")
    finally:
        await bot.session.close()


def main() -> int:
    os.chdir(ROOT)
    load_dotenv()
    cfg = load_config("config.yaml")
    problems = check_setup(cfg, os.environ)
    if problems:
        for p in problems:
            print("❌", p, file=sys.stderr)
        return 1
    setup_logging(cfg.log_path)
    Path("data").mkdir(exist_ok=True)
    with open("data/run.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.getLogger("job_hunter").info("previous run still in progress, skip")
            return 0
        logging.getLogger("job_hunter").info("старт прогона (первый прогон с оценкой может идти 5-10 минут)")
        asyncio.run(amain())
    return 0


if __name__ == "__main__":
    sys.exit(main())
