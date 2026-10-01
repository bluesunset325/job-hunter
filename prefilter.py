import re

from config import SearchCfg
from models import Vacancy

MIN_HOURLY_USD = 10


def _pattern(words: list[str], whole_word: bool) -> re.Pattern | None:
    if not words:
        return None
    parts = [re.escape(w) for w in words]
    if whole_word:
        alt = "|".join(rf"(?<!\w){p}(?!\w)" for p in parts)
    else:
        alt = "|".join(rf"(?<!\w){p}" for p in parts)
    return re.compile(alt, re.IGNORECASE)


def keep(v: Vacancy, search: SearchCfg, rates: dict[str, float]) -> bool:
    if v.remote is False:
        return False
    text = f"{v.title} {v.description}"
    stop_re = _pattern(search.stop_words, whole_word=True)
    if stop_re and stop_re.search(text):
        return False
    kw_re = _pattern(search.keywords, whole_word=False)
    if not (kw_re and kw_re.search(text)):
        return False
    if v.kind == "job":
        top = v.salary_to or v.salary_from
        currency = (v.currency or "").upper()
        if top and currency in rates and top * rates[currency] < search.min_salary_rub:
            return False
    if v.kind == "freelance" and v.currency == "USD/h":
        top = v.salary_to or v.salary_from
        if top and top < MIN_HOURLY_USD:
            return False
    if v.kind == "freelance" and search.min_freelance_usd:
        top = v.salary_to or v.salary_from
        currency = (v.currency or "").upper()
        if (top and currency != "RUB" and currency in rates and "USD" in rates
                and top * rates[currency] / rates["USD"] < search.min_freelance_usd):
            return False
    return True
