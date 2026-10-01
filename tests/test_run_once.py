import logging

import aiohttp
import pytest

import run_once
from config import load_config


def _cfg(tmp_path):
    resume = tmp_path / "resume.md"
    resume.write_text("resume text", encoding="utf-8")
    cfg = load_config("config.yaml")
    cfg.db_path = str(tmp_path / "t.db")
    cfg.resume_path = str(resume)
    return cfg


async def test_amain_logs_and_does_not_raise_on_run_failure(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("JH_BOT_TOKEN", "123:ABC")
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(run_once, "load_config", lambda path: cfg)
    monkeypatch.setattr(run_once, "build_sources", lambda c: [])

    async def boom(*a, **kw):
        raise RuntimeError("pipeline exploded")

    monkeypatch.setattr(run_once, "run", boom)

    closed = []

    async def fake_close(self):
        closed.append(True)

    monkeypatch.setattr("aiogram.client.session.aiohttp.AiohttpSession.close", fake_close)

    with caplog.at_level(logging.ERROR, logger="job_hunter"):
        await run_once.amain()

    assert any("run failed" in r.message for r in caplog.records)
    assert closed == [True]


async def test_source_timeout_allows_sock_connect_within_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("JH_BOT_TOKEN", "123:ABC")
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(run_once, "load_config", lambda path: cfg)
    monkeypatch.setattr(run_once, "build_sources", lambda c: [])

    seen = {}
    real_client_session = aiohttp.ClientSession

    def spy_session(*a, **kw):
        seen["timeout"] = kw.get("timeout")
        return real_client_session(*a, **kw)

    async def fake_run(*a, **kw):
        return None

    monkeypatch.setattr(run_once, "run", fake_run)
    monkeypatch.setattr(run_once.aiohttp, "ClientSession", spy_session)

    async def fake_close(self):
        pass

    monkeypatch.setattr("aiogram.client.session.aiohttp.AiohttpSession.close", fake_close)

    await run_once.amain()

    assert seen["timeout"].total == 20
    assert seen["timeout"].sock_connect == 10


def test_check_setup_ok(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.telegram.chat_id = 123456789
    assert run_once.check_setup(cfg, {"JH_BOT_TOKEN": "7123456789:AAHrealtoken"}) == []


def test_check_setup_reports_placeholder_chat_id_and_token(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.telegram.chat_id = 0
    problems = run_once.check_setup(cfg, {"JH_BOT_TOKEN": "123456:ABC..."})
    assert len(problems) == 2
    assert any("chat_id" in p for p in problems)
    assert any("JH_BOT_TOKEN" in p for p in problems)


def test_check_setup_reports_missing_token(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.telegram.chat_id = 5
    problems = run_once.check_setup(cfg, {})
    assert len(problems) == 1 and "JH_BOT_TOKEN" in problems[0]
