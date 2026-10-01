import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from models import ScoreResult, Vacancy, dedup_hash

DEDUP_WINDOW = timedelta(days=14)
SENT_STATUSES = ("sent", "starred", "applied", "hidden")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vacancies(
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL, external_id TEXT NOT NULL, url TEXT NOT NULL,
  title TEXT NOT NULL, company TEXT NOT NULL DEFAULT '',
  salary_from INTEGER, salary_to INTEGER, currency TEXT,
  remote INTEGER, description TEXT NOT NULL DEFAULT '',
  published_at TEXT NOT NULL, kind TEXT NOT NULL,
  dedup_hash TEXT NOT NULL,
  score INTEGER, why TEXT, red_flags TEXT, salary_guess TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL, tg_message_id INTEGER,
  UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS ix_vac_hash ON vacancies(dedup_hash);
CREATE INDEX IF NOT EXISTS ix_vac_status ON vacancies(status);
CREATE TABLE IF NOT EXISTS source_state(
  source TEXT PRIMARY KEY, last_success_at TEXT,
  consecutive_failures INTEGER NOT NULL DEFAULT 0, alerted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""


@dataclass
class SourceState:
    last_success_at: datetime | None
    consecutive_failures: int
    alerted: bool


class Storage:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(_SCHEMA)

    def add(self, v: Vacancy, now: datetime, status: str = "pending") -> int | None:
        h = dedup_hash(v.title, v.company, v.description)
        if self.db.execute("SELECT 1 FROM vacancies WHERE source=? AND external_id=?",
                           (v.source, v.external_id)).fetchone():
            return None
        if self.db.execute("SELECT 1 FROM vacancies WHERE dedup_hash=? AND created_at>=?",
                           (h, (now - DEDUP_WINDOW).isoformat())).fetchone():
            return None
        cur = self.db.execute(
            "INSERT INTO vacancies(source, external_id, url, title, company, salary_from, salary_to,"
            " currency, remote, description, published_at, kind, dedup_hash, status, created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (v.source, v.external_id, v.url, v.title, v.company, v.salary_from, v.salary_to,
             v.currency, None if v.remote is None else int(v.remote), v.description,
             v.published_at.isoformat(), v.kind, h, status, now.isoformat()))
        self.db.commit()
        return cur.lastrowid

    def get(self, id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM vacancies WHERE id=?", (id,)).fetchone()

    def set_status(self, id: int, status: str) -> None:
        self.db.execute("UPDATE vacancies SET status=? WHERE id=?", (status, id))
        self.db.commit()

    def set_score(self, id: int, r: ScoreResult) -> None:
        self.db.execute(
            "UPDATE vacancies SET score=?, why=?, red_flags=?, salary_guess=?, status='scored'"
            " WHERE id=?",
            (r.score, r.why, json.dumps(r.red_flags, ensure_ascii=False), r.salary_guess, id))
        self.db.commit()

    def mark_sent(self, id: int, message_id: int) -> None:
        self.db.execute("UPDATE vacancies SET status='sent', tg_message_id=? WHERE id=?",
                        (message_id, id))
        self.db.commit()

    def pending(self, limit: int) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM vacancies WHERE status='pending' ORDER BY id LIMIT ?",
                               (limit,)).fetchall()

    def to_send(self, threshold: int, limit: int) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM vacancies WHERE status='scored' AND (score>=? OR score IS NULL)"
            " ORDER BY score IS NULL, score DESC, id LIMIT ?", (threshold, limit)).fetchall()

    def top(self, since: datetime, limit: int) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM vacancies WHERE score IS NOT NULL AND created_at>=? AND status!='hidden'"
            " ORDER BY score DESC, id LIMIT ?", (since.isoformat(), limit)).fetchall()

    def below_threshold(self, threshold: int, limit: int) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM vacancies WHERE status='scored' AND score<? ORDER BY id DESC LIMIT ?",
            (threshold, limit)).fetchall()

    def starred(self) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM vacancies WHERE status='starred' ORDER BY id DESC").fetchall()

    def stats(self, since: datetime) -> dict[str, dict[str, int]]:
        marks = ",".join("?" * len(SENT_STATUSES))
        rows = self.db.execute(
            f"SELECT source, COUNT(*) AS collected,"
            f" SUM(status!='filtered') AS passed,"
            f" SUM(status IN ({marks})) AS sent"
            f" FROM vacancies WHERE created_at>=? GROUP BY source ORDER BY source",
            (*SENT_STATUSES, since.isoformat())).fetchall()
        return {r["source"]: {"collected": r["collected"], "passed": r["passed"], "sent": r["sent"]}
                for r in rows}

    def source_state(self, name: str) -> SourceState:
        r = self.db.execute("SELECT * FROM source_state WHERE source=?", (name,)).fetchone()
        if not r:
            return SourceState(None, 0, False)
        last = datetime.fromisoformat(r["last_success_at"]) if r["last_success_at"] else None
        return SourceState(last, r["consecutive_failures"], bool(r["alerted"]))

    def record_success(self, name: str, at: datetime) -> None:
        self.db.execute(
            "INSERT INTO source_state(source, last_success_at, consecutive_failures, alerted)"
            " VALUES(?,?,0,0) ON CONFLICT(source) DO UPDATE SET last_success_at=excluded.last_success_at,"
            " consecutive_failures=0, alerted=0", (name, at.isoformat()))
        self.db.commit()

    def record_failure(self, name: str) -> int:
        self.db.execute(
            "INSERT INTO source_state(source, consecutive_failures) VALUES(?,1)"
            " ON CONFLICT(source) DO UPDATE SET consecutive_failures=consecutive_failures+1", (name,))
        self.db.commit()
        return self.source_state(name).consecutive_failures

    def mark_alerted(self, name: str) -> None:
        self.db.execute("UPDATE source_state SET alerted=1 WHERE source=?", (name,))
        self.db.commit()

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        r = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set_setting(self, key: str, value: str) -> None:
        self.db.execute("INSERT INTO settings(key, value) VALUES(?,?)"
                        " ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        self.db.commit()

    @staticmethod
    def row_to_vacancy(row: sqlite3.Row) -> Vacancy:
        return Vacancy(
            source=row["source"], external_id=row["external_id"], url=row["url"],
            title=row["title"], company=row["company"],
            published_at=datetime.fromisoformat(row["published_at"]), kind=row["kind"],
            remote=None if row["remote"] is None else bool(row["remote"]),
            salary_from=row["salary_from"], salary_to=row["salary_to"], currency=row["currency"],
            description=row["description"])
