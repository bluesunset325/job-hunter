import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from config import Config
from prefilter import keep
from scorer import OllamaUnavailable
from storage import Storage

log = logging.getLogger("job_hunter")
FAIL_ALERT_AFTER = 3
FIRST_RUN_LOOKBACK = timedelta(days=7)
OVERLAP = timedelta(hours=24)
SEND_DELAY = 1.0


class PermanentSendError(Exception):
    pass


class RetryLater(Exception):
    def __init__(self, seconds: float):
        super().__init__(f"retry after {seconds}s")
        self.seconds = seconds


class Notifier(Protocol):
    async def send_card(self, row) -> int: ...
    async def send_text(self, text: str) -> None: ...


@dataclass
class RunReport:
    fetched: dict[str, int] = field(default_factory=dict)
    new: int = 0
    filtered: int = 0
    scored: int = 0
    sent: int = 0
    failed: list[str] = field(default_factory=list)


async def run(sources, http, storage: Storage, scorer, notifier: Notifier, cfg: Config,
              now: datetime, source_timeout: float = 60) -> RunReport:
    rep = RunReport()
    states = {s.name: storage.source_state(s.name) for s in sources}
    results = await asyncio.gather(
        *(asyncio.wait_for(s.fetch(http), source_timeout) for s in sources), return_exceptions=True)

    for src, res in zip(sources, results):
        state = states[src.name]
        if isinstance(res, BaseException):
            log.warning("source %s failed: %r", src.name, res)
            rep.failed.append(src.name)
            n = storage.record_failure(src.name)
            if n >= FAIL_ALERT_AFTER and not state.alerted:
                try:
                    await notifier.send_text(
                        f"⚠️ Источник {src.name} падает {n} раза подряд: {res!r}"[:500])
                except Exception:
                    log.exception("failed to send failure alert for %s", src.name)
                else:
                    storage.mark_alerted(src.name)
            continue
        storage.record_success(src.name, now)
        rep.fetched[src.name] = len(res)
        log.info("%s: собрано %d", src.name, len(res))
        since = (state.last_success_at - OVERLAP if state.last_success_at
                 else now - FIRST_RUN_LOOKBACK)
        for v in res:
            if v.published_at < since:
                continue
            ok = keep(v, cfg.search, cfg.rates)
            if storage.add(v, now, "pending" if ok else "filtered") is not None:
                rep.new += 1
                rep.filtered += 0 if ok else 1

    log.info("новых %d, отсеяно фильтром %d", rep.new, rep.filtered)
    pending = storage.pending(cfg.scoring.max_score_per_run)
    for i, row in enumerate(pending, 1):
        log.info("оцениваю %d/%d: %s", i, len(pending), row["title"][:60])
        try:
            result = await scorer.score(Storage.row_to_vacancy(row))
        except OllamaUnavailable as e:
            log.warning("ollama unavailable, scoring postponed: %s", e)
            break
        storage.set_score(row["id"], result)
        rep.scored += 1

    if storage.get_setting("paused", "0") == "1":
        log.info("рассылка на паузе, карточки не отправляются")
        return rep
    for row in storage.to_send(cfg.scoring.score_threshold, cfg.scoring.max_per_run):
        try:
            storage.mark_sent(row["id"], await notifier.send_card(row))
            rep.sent += 1
        except RetryLater as e:
            log.warning("rate limited sending card %s, retrying in %.1fs", row["id"], e.seconds)
            await asyncio.sleep(e.seconds)
            try:
                storage.mark_sent(row["id"], await notifier.send_card(row))
                rep.sent += 1
            except Exception:
                log.exception("failed to send card %s after retry, stopping", row["id"])
                break
        except PermanentSendError as e:
            log.warning("permanent send error for card %s: %s", row["id"], e)
            storage.set_status(row["id"], "send_failed")
        except Exception:
            log.exception("failed to send card %s", row["id"])
        await asyncio.sleep(SEND_DELAY)
    log.info("отправлено %d", rep.sent)
    return rep
