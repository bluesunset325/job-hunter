import asyncio
from datetime import datetime, timezone

import aiohttp
import pytest

from models import ScoreResult, Vacancy
from scorer import OllamaUnavailable, Scorer, build_prompt, parse_llm_json

V = Vacancy(source="hh", external_id="1", url="u", title="Python-разработчик (боты)",
            company="Ромашка", published_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
            description="aiogram, PostgreSQL", salary_to=150000, currency="RUB")


def test_parse_valid():
    r = parse_llm_json('{"score": 82, "why": "aiogram", "red_flags": ["Kafka"], "salary_guess": "150k"}')
    assert r == ScoreResult(82, "aiogram", ["Kafka"], "150k")


def test_parse_wrapped_and_clamped():
    r = parse_llm_json('```json\n{"score": "140", "why": "x"}\n```')
    assert r.score == 100 and r.red_flags == [] and r.salary_guess == ""


@pytest.mark.parametrize("bad", ["", "не знаю", '{"why": "no score"}', '{"score": "abc"}', "[1,2]"])
def test_parse_invalid(bad):
    assert parse_llm_json(bad) is None


def test_prompt_contains_resume_and_vacancy():
    p = build_prompt("МОЁ РЕЗЮМЕ", V)
    assert "МОЁ РЕЗЮМЕ" in p and "Python-разработчик (боты)" in p and "Ромашка" in p
    assert "150000" in p


def reply(content):
    return {"message": {"content": content}}


async def test_score_ok():
    async def post(url, payload):
        assert url == "http://o/api/chat" and payload["format"] == "json"
        return reply('{"score": 70, "why": "ok", "red_flags": [], "salary_guess": ""}')

    r = await Scorer("http://o", "m", 5, "resume", post=post).score(V)
    assert r.score == 70


async def test_score_retries_once_then_unscored():
    calls = []

    async def post(url, payload):
        calls.append(1)
        return reply("мусор")

    r = await Scorer("http://o", "m", 5, "resume", post=post).score(V)
    assert len(calls) == 2
    assert r.score is None and r.why.startswith("не оценено")


async def test_score_unavailable():
    async def post(url, payload):
        raise aiohttp.ClientConnectionError("refused")

    with pytest.raises(OllamaUnavailable):
        await Scorer("http://o", "m", 5, "resume", post=post).score(V)


async def test_score_client_response_error_unavailable():
    async def post(url, payload):
        raise aiohttp.ClientResponseError(request_info=None, history=(), status=500)

    with pytest.raises(OllamaUnavailable):
        await Scorer("http://o", "m", 5, "resume", post=post).score(V)


async def test_score_timeout_is_per_item_unscored_not_unavailable():
    async def post(url, payload):
        raise asyncio.TimeoutError()

    r = await Scorer("http://o", "m", 5, "resume", post=post).score(V)
    assert r.score is None and r.why == "не оценено: таймаут модели"


async def test_options_include_num_predict():
    seen = {}

    async def post(url, payload):
        seen.update(payload)
        return reply('{"score": 70, "why": "ok"}')

    await Scorer("http://o", "m", 5, "resume", post=post).score(V)
    assert seen["options"]["num_predict"] == 512


def test_prompt_includes_candidate_notes():
    p = build_prompt("resume", V, notes="Английский B1")
    assert "О КАНДИДАТЕ" in p and "Английский B1" in p
    assert "О КАНДИДАТЕ" not in build_prompt("resume", V)


async def test_scorer_passes_notes_into_prompt():
    seen = {}

    async def post(url, payload):
        seen["prompt"] = payload["messages"][1]["content"]
        return reply('{"score": 70, "why": "ok", "red_flags": [], "salary_guess": ""}')

    await Scorer("http://o", "m", 5, "resume", notes="Английский B1", post=post).score(V)
    assert "Английский B1" in seen["prompt"]
