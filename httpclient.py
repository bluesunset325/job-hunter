import asyncio
import json
from typing import Any

import aiohttp

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")


class _Retryable(Exception):
    pass


_RETRY_ON = (
    _Retryable,
    aiohttp.ClientConnectionError,
    aiohttp.ClientPayloadError,
    asyncio.TimeoutError,
)


class Http:
    def __init__(self, session: aiohttp.ClientSession | None, retries: int = 2,
                 backoff: float = 1.0):
        self.session = session
        self.retries = retries
        self.backoff = backoff

    async def _once(self, url: str, params: dict | None) -> str:
        async with self.session.get(url, params=params, headers={"User-Agent": UA}) as r:
            if r.status == 429 or r.status >= 500:
                raise _Retryable(f"HTTP {r.status} {url}")
            r.raise_for_status()
            return await r.text()

    async def get_text(self, url: str, params: dict | None = None) -> str:
        for attempt in range(self.retries + 1):
            try:
                return await self._once(url, params)
            except _RETRY_ON:
                if attempt == self.retries:
                    raise
                await asyncio.sleep(self.backoff * 2 ** attempt)
        raise AssertionError("unreachable")

    async def get_json(self, url: str, params: dict | None = None) -> Any:
        return json.loads(await self.get_text(url, params))
