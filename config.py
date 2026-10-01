from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class TelegramCfg:
    bot_token_env: str
    chat_id: int


@dataclass
class TelethonCfg:
    api_id_env: str
    api_hash_env: str
    session_path: str
    channels: list[str]


@dataclass
class OllamaCfg:
    url: str
    model: str
    timeout_s: int


@dataclass
class SearchCfg:
    query: str
    keywords: list[str]
    stop_words: list[str]
    min_salary_rub: int
    min_freelance_usd: int = 0


@dataclass
class ScoringCfg:
    score_threshold: int
    max_per_run: int
    max_score_per_run: int


@dataclass
class Config:
    telegram: TelegramCfg
    telethon: TelethonCfg
    ollama: OllamaCfg
    search: SearchCfg
    scoring: ScoringCfg
    rates: dict[str, float]
    sources: dict[str, bool]
    db_path: str
    resume_path: str
    log_path: str
    candidate_notes: str = ""


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Config(
        telegram=TelegramCfg(**raw["telegram"]),
        telethon=TelethonCfg(**{**raw["telethon"], "channels": raw["telethon"].get("channels") or []}),
        ollama=OllamaCfg(**raw["ollama"]),
        search=SearchCfg(**raw["search"]),
        scoring=ScoringCfg(**raw["scoring"]),
        rates={k.upper(): float(v) for k, v in raw["rates"].items()},
        sources=dict(raw["sources"]),
        db_path=raw["db_path"],
        resume_path=raw["resume_path"],
        log_path=raw["log_path"],
        candidate_notes=(raw.get("candidate_notes") or "").strip(),
    )
