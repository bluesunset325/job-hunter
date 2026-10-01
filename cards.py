import json
from datetime import datetime
from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SOURCE_TITLES = {"hh": "hh.ru", "habr_career": "Habr Career", "getmatch": "GetMatch",
                 "remoteok": "RemoteOK", "wwr": "WeWorkRemotely", "himalayas": "Himalayas",
                 "kwork": "Kwork", "fl": "FL.ru", "telegram": "Telegram",
                 "freelancer": "Freelancer.com", "pph": "PeoplePerHour", "remotive": "Remotive",
                 "jobicy": "Jobicy"}
_SYMBOLS = {"RUB": "₽", "USD": "$", "EUR": "€", "GBP": "£", "USD/h": "$/ч"}


def humanize_age(published_at: datetime, now: datetime) -> str:
    hours = int((now - published_at).total_seconds() // 3600)
    if hours < 1:
        return "только что"
    if hours < 24:
        return f"{hours} ч назад"
    return f"{hours // 24} дн назад"


def _amount(x: int) -> str:
    return f"{round(x / 1000)}k" if x >= 10000 else str(x)


def _salary(r) -> str:
    sym = _SYMBOLS.get(r["currency"] or "", r["currency"] or "")
    lo, hi = r["salary_from"], r["salary_to"]
    if lo and hi:
        # k только у верхней границы: 120–160k
        lo_str = f"{round(lo / 1000)}" if lo >= 10000 else str(lo)
        hi_str = f"{round(hi / 1000)}k" if hi >= 10000 else str(hi)
        return f"{lo_str}–{hi_str} {sym}".strip()
    if lo:
        return f"от {_amount(lo)} {sym}".strip()
    if hi:
        return f"до {_amount(hi)} {sym}".strip()
    if r["salary_guess"]:
        return f"~{r['salary_guess']}"
    return "не указана"


def _emoji(score) -> str:
    if score is None:
        return "⚪"
    return "🟢" if score >= 80 else "🟡" if score >= 65 else "🔴"


def format_card(r, now: datetime) -> str:
    score = r["score"]
    remote = {1: "удалёнка", 0: "офис"}.get(r["remote"], "удалёнка?")
    head = (f"{_emoji(score)} {score if score is not None else '—'} · "
            f"{'💼' if r['kind'] == 'freelance' else ''}<b>{escape(r['title'])}</b>"
            + (f" — {escape(r['company'])}" if r["company"] else ""))
    age = humanize_age(datetime.fromisoformat(r["published_at"]), now)
    lines = [head, f"💰 {escape(_salary(r))} · 🌍 {remote} · "
                   f"{SOURCE_TITLES.get(r['source'], r['source'])} · {age}"]
    if r["why"]:
        lines.append(f"✅ {escape(r['why'][:400])}")
    flags = json.loads(r["red_flags"] or "[]")
    if flags:
        lines.append(f"⚠️ {escape('; '.join(flags)[:400])}")
    return "\n".join(lines)


def card_keyboard(r) -> InlineKeyboardMarkup:
    i = r["id"]
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть", url=r["url"]),
        InlineKeyboardButton(text="⭐", callback_data=f"st:{i}:starred"),
        InlineKeyboardButton(text="✅ Откликнулся", callback_data=f"st:{i}:applied"),
        InlineKeyboardButton(text="🙈 Скрыть", callback_data=f"st:{i}:hidden"),
    ]])
