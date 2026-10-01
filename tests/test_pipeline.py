import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import pipeline
from config import load_config
from models import ScoreResult, Vacancy
from pipeline import PermanentSendError, RetryLater, run
from scorer import OllamaUnavailable
from sources.base import Source
from storage import Storage

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


def vac(ext, title="Python developer", age_h=1, **kw):
    return Vacancy(source="fake", external_id=ext, url=f"https://x/{ext}", title=title,
                   company=f"C{ext}", published_at=NOW - timedelta(hours=age_h), remote=True, **kw)


class FakeSource(Source):
    def __init__(self, name, items=None, error=None, delay=0):
        self.name, self.items, self.error, self.delay = name, items or [], error, delay

    async def fetch(self, http):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.items


class FakeScorer:
    def __init__(self, scores=None, unavailable_after=None):
        self.scores, self.calls, self.unavailable_after = scores or {}, 0, unavailable_after

    async def score(self, v):
        if self.unavailable_after is not None and self.calls >= self.unavailable_after:
            raise OllamaUnavailable("down")
        self.calls += 1
        return ScoreResult(self.scores.get(v.external_id, 90), "ok", [], "")


class FakeNotifier:
    def __init__(self):
        self.cards, self.texts = [], []

    async def send_card(self, row):
        self.cards.append(row["external_id"])
        return 1000 + len(self.cards)

    async def send_text(self, text):
        self.texts.append(text)


@pytest.fixture(autouse=True)
def fast_send_delay(monkeypatch):
    monkeypatch.setattr(pipeline, "SEND_DELAY", 0)


@pytest.fixture
def env(tmp_path):
    cfg = load_config("config.yaml")
    cfg.scoring.max_per_run = 2
    return Storage(str(tmp_path / "t.db")), cfg, FakeNotifier()


async def test_full_flow(env):
    st, cfg, nt = env
    src = FakeSource("fake", [vac("1"), vac("2"), vac("3"), vac("4", title="Java dev"),
                              vac("old", age_h=24 * 8)])
    rep = await run([src], None, st, FakeScorer({"1": 95, "2": 70, "3": 20}), nt, cfg, NOW)
    assert rep.fetched == {"fake": 5}
    assert rep.new == 4 and rep.filtered == 1 and rep.scored == 3 and rep.sent == 2
    assert nt.cards == ["1", "2"]
    assert st.source_state("fake").last_success_at == NOW


async def test_second_run_no_duplicates(env):
    st, cfg, nt = env
    src = FakeSource("fake", [vac("1")])
    await run([src], None, st, FakeScorer(), nt, cfg, NOW)
    rep = await run([src], None, st, FakeScorer(), nt, cfg, NOW + timedelta(minutes=30))
    assert rep.new == 0 and nt.cards == ["1"]


async def test_failing_source_alerts_once_after_three(env):
    st, cfg, nt = env
    bad = FakeSource("bad", error=RuntimeError("boom"))
    good = FakeSource("fake", [vac("1")])
    for i in range(4):
        rep = await run([bad, good], None, st, FakeScorer(), nt, cfg, NOW + timedelta(hours=i))
        assert rep.failed == ["bad"]
    assert len(nt.texts) == 1 and "bad" in nt.texts[0] and "3" in nt.texts[0]


async def test_timeout_counts_as_failure(env):
    st, cfg, nt = env
    rep = await run([FakeSource("slow", delay=1)], None, st, FakeScorer(), nt, cfg, NOW,
                    source_timeout=0.01)
    assert rep.failed == ["slow"]


async def test_ollama_down_keeps_pending(env):
    st, cfg, nt = env
    src = FakeSource("fake", [vac("1"), vac("2")])
    rep = await run([src], None, st, FakeScorer(unavailable_after=1), nt, cfg, NOW)
    assert rep.scored == 1
    assert [r["external_id"] for r in st.pending(10)] == ["2"]


async def test_paused_does_not_send(env):
    st, cfg, nt = env
    st.set_setting("paused", "1")
    rep = await run([FakeSource("fake", [vac("1")])], None, st, FakeScorer(), nt, cfg, NOW)
    assert rep.sent == 0 and nt.cards == []


async def test_late_appearing_item_within_24h_overlap_is_added(env):
    st, cfg, nt = env
    await run([FakeSource("fake", [vac("1")])], None, st, FakeScorer(), nt, cfg, NOW)
    late = vac("late", age_h=2)  # вышла раньше прошлого прогона, но в ленте появилась позже
    rep = await run([FakeSource("fake", [late])], None, st, FakeScorer(), nt, cfg,
                    NOW + timedelta(minutes=30))
    assert rep.new == 1


async def test_send_text_failure_does_not_crash_run_and_alerted_stays_false(env):
    st, cfg, nt = env

    class BadTextNotifier(FakeNotifier):
        async def send_text(self, text):
            raise RuntimeError("telegram down")

    nt2 = BadTextNotifier()
    bad = FakeSource("bad", error=RuntimeError("boom"))
    good = FakeSource("fake", [vac("1")])
    for i in range(3):
        rep = await run([bad, good], None, st, FakeScorer(), nt2, cfg, NOW + timedelta(hours=i))
    assert rep.failed == ["bad"]
    assert nt2.cards == ["1"]
    assert st.source_state("bad").alerted is False


async def test_send_loop_sleeps_between_cards(env, monkeypatch):
    st, cfg, nt = env
    monkeypatch.setattr(pipeline, "SEND_DELAY", 0)
    sleeps = []
    real_sleep = asyncio.sleep

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(pipeline.asyncio, "sleep", fake_sleep)
    src = FakeSource("fake", [vac("1"), vac("2")])
    rep = await run([src], None, st, FakeScorer(), nt, cfg, NOW)
    assert rep.sent == 2
    assert sleeps == [0, 0]


async def test_retry_after_then_success(env, monkeypatch):
    st, cfg, nt = env
    monkeypatch.setattr(pipeline, "SEND_DELAY", 0)

    class RetryOnceNotifier(FakeNotifier):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        async def send_card(self, row):
            self.attempts += 1
            if self.attempts == 1:
                raise RetryLater(0)
            return await super().send_card(row)

    nt2 = RetryOnceNotifier()
    src = FakeSource("fake", [vac("1")])
    rep = await run([src], None, st, FakeScorer(), nt2, cfg, NOW)
    assert rep.sent == 1
    assert nt2.attempts == 2


async def test_retry_fails_again_stops_send_loop(env, monkeypatch):
    st, cfg, nt = env
    monkeypatch.setattr(pipeline, "SEND_DELAY", 0)

    class AlwaysRetryNotifier(FakeNotifier):
        async def send_card(self, row):
            raise RetryLater(0)

    nt2 = AlwaysRetryNotifier()
    src = FakeSource("fake", [vac("1"), vac("2")])
    rep = await run([src], None, st, FakeScorer(), nt2, cfg, NOW)
    assert rep.sent == 0
    assert len(st.to_send(cfg.scoring.score_threshold, 10)) == 2


async def test_permanent_send_error_marks_send_failed_and_continues(env, monkeypatch):
    st, cfg, nt = env
    monkeypatch.setattr(pipeline, "SEND_DELAY", 0)

    class PermanentFailNotifier(FakeNotifier):
        async def send_card(self, row):
            if row["external_id"] == "1":
                raise PermanentSendError("bad request")
            return await super().send_card(row)

    nt2 = PermanentFailNotifier()
    src = FakeSource("fake", [vac("1"), vac("2")])
    rep = await run([src], None, st, FakeScorer(), nt2, cfg, NOW)
    assert rep.sent == 1
    assert nt2.cards == ["2"]
    row1 = st.db.execute("SELECT status FROM vacancies WHERE external_id='1'").fetchone()
    assert row1["status"] == "send_failed"


async def test_logs_progress_at_info(env, caplog):
    import logging

    st, cfg, nt = env
    src = FakeSource("fake", [vac("1"), vac("2"), vac("4", title="Java dev")])
    with caplog.at_level(logging.INFO, logger="job_hunter"):
        await run([src], None, st, FakeScorer({"1": 95, "2": 70}), nt, cfg, NOW)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "fake: собрано 3" in text
    assert "новых 3, отсеяно фильтром 1" in text
    assert "оцениваю 1/2" in text and "оцениваю 2/2" in text
    assert "отправлено 2" in text


async def test_first_run_looks_back_seven_days(env):
    st, cfg, nt = env
    src = FakeSource("fake", [vac("6d", age_h=24 * 6), vac("8d", age_h=24 * 8)])
    rep = await run([src], None, st, FakeScorer(), nt, cfg, NOW)
    assert rep.new == 1
