import html
import re

_SPACES = re.compile(r"[   ]")
_NUM = r"(\d{1,3}(?: \d{3})+|\d+)\s*(к|k|тыс\.?)?"
_CUR = r"(₽|руб\.?|р\.|rub|rur|\$|usd|€|eur)"
_RANGE = re.compile(rf"(?:от\s*)?{_NUM}\s*(?:-|–|—|до)\s*{_NUM}\s*{_CUR}", re.I)
_FROM = re.compile(rf"от\s*{_NUM}\s*{_CUR}", re.I)
_TO = re.compile(rf"до\s*{_NUM}\s*{_CUR}", re.I)
_CUR_CODES = {"₽": "RUB", "руб": "RUB", "руб.": "RUB", "р.": "RUB", "rub": "RUB", "rur": "RUB",
              "$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR"}
_TAG = re.compile(r"<[^>]+>")


def _num(digits: str, mult: str | None) -> int:
    value = int(digits.replace(" ", ""))
    return value * 1000 if mult else value


def parse_salary(text: str) -> tuple[int | None, int | None, str | None]:
    t = _SPACES.sub(" ", text)
    if m := _RANGE.search(t):
        mult = m.group(2) or m.group(4)
        return _num(m.group(1), mult), _num(m.group(3), m.group(4)), _CUR_CODES[m.group(5).lower()]
    lo = _FROM.search(t)
    hi = _TO.search(t)
    if lo or hi:
        cur = (lo or hi).group(3).lower()
        return (_num(lo.group(1), lo.group(2)) if lo else None,
                _num(hi.group(1), hi.group(2)) if hi else None,
                _CUR_CODES[cur])
    return None, None, None


def strip_html(text: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", text or ""))).strip()
