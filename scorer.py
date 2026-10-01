import asyncio
import json
import re

import aiohttp

from models import ScoreResult, Vacancy

SYSTEM = (
    "Ты помогаешь Python-разработчику искать удалённую работу. Оцени, насколько вакансия "
    "подходит кандидату по резюме. Отвечай ТОЛЬКО JSON-объектом без пояснений:\n"
    '{"score": <целое 0-100>, "why": "<1-2 коротких предложения по-русски: что совпадает>", '
    '"red_flags": ["<короткие минусы: не тот стек, нужен большой опыт, офис, низкая оплата…>"], '
    '"salary_guess": "<вилка из текста или твоя оценка, например \'150–200k ₽\', или пусто>"}\n'
    "Шкала: 85+ — почти идеально; 65–84 — стоит откликнуться; 40–64 — сомнительно; <40 — не подходит."
)
_OBJ = re.compile(r"\{.*\}", re.S)


class OllamaUnavailable(Exception):
    pass


def parse_llm_json(text: str) -> ScoreResult | None:
    m = _OBJ.search(text or "")
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        score = max(0, min(100, int(d["score"])))
    except (ValueError, KeyError, TypeError):
        return None
    flags = d.get("red_flags") or []
    return ScoreResult(score=score, why=str(d.get("why", "")).strip(),
                       red_flags=[str(f) for f in flags] if isinstance(flags, list) else [str(flags)],
                       salary_guess=str(d.get("salary_guess") or "").strip())


def build_prompt(resume: str, v: Vacancy, notes: str = "") -> str:
    salary = ""
    if v.salary_from or v.salary_to:
        salary = f"{v.salary_from or ''}–{v.salary_to or ''} {v.currency or ''}"
    return (f"РЕЗЮМЕ КАНДИДАТА:\n{resume[:6000]}\n\n"
            + (f"О КАНДИДАТЕ: {notes}\n\n" if notes else "")
            + f"ВАКАНСИЯ ({'фриланс-заказ' if v.kind == 'freelance' else 'работа'}, "
            f"источник {v.source}):\n"
            f"Название: {v.title}\nКомпания: {v.company or '—'}\nЗарплата/бюджет: {salary or 'не указана'}\n"
            f"Удалёнка: {'да' if v.remote else 'неизвестно' if v.remote is None else 'нет'}\n"
            f"Описание:\n{v.description[:4000]}")


class Scorer:
    def __init__(self, url: str, model: str, timeout_s: int, resume: str, notes: str = "",
                 post=None):
        self.url = url.rstrip("/") + "/api/chat"
        self.model = model
        self.timeout_s = timeout_s
        self.resume = resume
        self.notes = notes
        self._post = post or self._http_post

    async def _http_post(self, url: str, payload: dict) -> dict:
        timeout = aiohttp.ClientTimeout(total=self.timeout_s)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.post(url, json=payload) as r:
                r.raise_for_status()
                return await r.json()

    async def score(self, v: Vacancy) -> ScoreResult:
        payload = {
            "model": self.model, "stream": False, "format": "json", "think": False,
            "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 512},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": build_prompt(self.resume, v, self.notes)}],
        }
        for _ in range(2):
            try:
                resp = await self._post(self.url, payload)
            except asyncio.TimeoutError:
                return ScoreResult(None, "не оценено: таймаут модели", [], "")
            except aiohttp.ClientError as e:
                raise OllamaUnavailable(repr(e)) from e
            result = parse_llm_json(resp.get("message", {}).get("content", ""))
            if result:
                return result
        return ScoreResult(None, "не оценено: модель вернула не JSON", [], "")
