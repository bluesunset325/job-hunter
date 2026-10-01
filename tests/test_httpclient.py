import aiohttp
import pytest

from httpclient import Http, _Retryable


async def test_retries_then_succeeds(monkeypatch):
    calls = []

    async def fake_once(self, url, params):
        calls.append(url)
        if len(calls) < 3:
            raise _Retryable("503")
        return "ok"

    monkeypatch.setattr(Http, "_once", fake_once)
    http = Http(session=None, retries=2, backoff=0)
    assert await http.get_text("https://x") == "ok"
    assert len(calls) == 3


async def test_gives_up_after_retries(monkeypatch):
    async def fake_once(self, url, params):
        raise aiohttp.ClientConnectionError("down")

    monkeypatch.setattr(Http, "_once", fake_once)
    with pytest.raises(aiohttp.ClientConnectionError):
        await Http(session=None, retries=2, backoff=0).get_text("https://x")


async def test_retries_on_client_payload_error(monkeypatch):
    calls = []

    async def fake_once(self, url, params):
        calls.append(url)
        if len(calls) < 2:
            raise aiohttp.ClientPayloadError("truncated read")
        return "ok"

    monkeypatch.setattr(Http, "_once", fake_once)
    http = Http(session=None, retries=2, backoff=0)
    assert await http.get_text("https://x") == "ok"
    assert len(calls) == 2


async def test_client_response_error_fails_immediately(monkeypatch):
    calls = []

    async def fake_once(self, url, params):
        calls.append(url)
        raise aiohttp.ClientResponseError(
            request_info=None, history=(), status=404
        )

    monkeypatch.setattr(Http, "_once", fake_once)
    with pytest.raises(aiohttp.ClientResponseError):
        await Http(session=None, retries=2, backoff=0).get_text("https://x")
    assert len(calls) == 1
