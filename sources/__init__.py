import os

from config import Config
from sources.base import Source

FREELANCER_QUERIES = ["python", "telegram bot", "web scraping", "automation", "parser"]


def build_sources(cfg: Config) -> list[Source]:
    from sources.foreign_freelance import (FreelancerComSource, JobicySource, PphSource,
                                           RemotiveSource)
    from sources.freelance import FlSource, KworkSource
    from sources.getmatch import GetMatchSource
    from sources.habr_career import HabrCareerSource
    from sources.hh import HhSource
    from sources.remote_boards import HimalayasSource, RemoteOkSource, WwrSource

    q = cfg.search.query
    factories = {
        "hh": lambda: HhSource(q),
        "habr_career": lambda: HabrCareerSource(q),
        "getmatch": lambda: GetMatchSource(),
        "remoteok": lambda: RemoteOkSource(),
        "wwr": lambda: WwrSource(),
        "himalayas": lambda: HimalayasSource(q),
        "kwork": lambda: KworkSource(),
        "fl": lambda: FlSource(),
        "freelancer": lambda: FreelancerComSource(FREELANCER_QUERIES),
        "pph": lambda: PphSource(),
        "remotive": lambda: RemotiveSource(q),
        "jobicy": lambda: JobicySource(q),
    }
    out = [make() for name, make in factories.items() if cfg.sources.get(name)]
    if cfg.sources.get("telegram"):
        from sources.telegram import TelegramSource
        out.append(TelegramSource(cfg.telethon, int(os.environ[cfg.telethon.api_id_env]),
                                  os.environ[cfg.telethon.api_hash_env]))
    return out
