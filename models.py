import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime

_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


@dataclass
class Vacancy:
    source: str
    external_id: str
    url: str
    title: str
    company: str
    published_at: datetime
    kind: str = "job"  # job или freelance
    remote: bool | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    currency: str | None = None
    description: str = ""


@dataclass
class ScoreResult:
    score: int | None
    why: str
    red_flags: list[str] = field(default_factory=list)
    salary_guess: str = ""


def _norm(text: str) -> str:
    return " ".join(_NON_WORD.sub(" ", text.lower()).replace("_", " ").split())


def dedup_hash(title: str, company: str, description: str = "") -> str:
    company_norm = _norm(company)
    part = company_norm if company_norm else _norm(description)[:200]
    return hashlib.sha1(f"{_norm(title)}|{part}".encode()).hexdigest()
