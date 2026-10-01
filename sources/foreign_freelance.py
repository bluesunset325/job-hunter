import logging
import re
from datetime import datetime, timedelta, timezone

from httpclient import Http
from models import Vacancy
from sources.base import Source
from textutil import strip_html

log = logging.getLogger("job_hunter")
_ITEM_ERRORS = (KeyError, TypeError, ValueError, AttributeError)


def _parse_iso_utc(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


class FreelancerComSource(Source):
    name = "freelancer"
    URL = "https://www.freelancer.com/api/projects/0.1/projects/active/"

    def __init__(self, queries: list[str]):
        self.queries = queries

    async def fetch(self, http: Http) -> list[Vacancy]:
        seen: dict[str, Vacancy] = {}
        for q in self.queries:
            data = await http.get_json(self.URL, {"query": q, "limit": 50,
                                                  "full_description": "true",
                                                  "sort_field": "time_updated"})
            for v in self.parse(data):
                seen.setdefault(v.external_id, v)
        return list(seen.values())

    @staticmethod
    def parse(data: dict) -> list[Vacancy]:
        out = []
        for p in (data.get("result") or {}).get("projects", []):
            try:
                rate = float(p["currency"].get("exchange_rate") or 1)
                budget = p.get("budget") or {}
                lo = round(budget["minimum"] * rate) if budget.get("minimum") else None
                hi = round(budget["maximum"] * rate) if budget.get("maximum") else None
                hourly = p.get("type") == "hourly"
                bids = (p.get("bid_stats") or {}).get("bid_count", 0)
                desc = p.get("description") or p.get("preview_description") or ""
                out.append(Vacancy(
                    source="freelancer", external_id=str(p["id"]),
                    url=f"https://www.freelancer.com/projects/{p['seo_url']}",
                    title=strip_html(p["title"]), company=f"откликов: {bids}",
                    published_at=datetime.fromtimestamp(p["time_submitted"], tz=timezone.utc),
                    kind="freelance", remote=True, salary_from=lo, salary_to=hi,
                    currency=("USD/h" if hourly else "USD") if (lo or hi) else None,
                    description=f"Оплата: {'почасовая' if hourly else 'фиксированная'}. "
                                f"Откликов: {bids}. {strip_html(desc)[:3500]}"))
            except _ITEM_ERRORS as e:
                log.warning("freelancer: skip malformed project: %r", e)
        return out


class PphSource(Source):
    name = "pph"
    URL = "https://www.peopleperhour.com/freelance-python-jobs"
    _CARD = re.compile(r'<li class="list__item')
    _LINK = re.compile(r'class="item__url[^"]*" href="([^"]+)">([^<]+)</a>')
    _DESC = re.compile(r'class="item__desc[^"]*">(.*?)</p>', re.S)
    _PRICE = re.compile(r'title-nano"><div><span>([^<]+)</span>')
    _AGE = re.compile(r"<span>(\d+ \w+ ago|an? \w+ ago|yesterday|today)</span>")
    _UNITS = {"minute": timedelta(minutes=1), "hour": timedelta(hours=1), "day": timedelta(days=1),
              "week": timedelta(weeks=1), "month": timedelta(days=30), "year": timedelta(days=365)}

    def __init__(self, now_fn=lambda: datetime.now(timezone.utc)):
        self.now_fn = now_fn

    async def fetch(self, http: Http) -> list[Vacancy]:
        return self.parse(await http.get_text(self.URL), self.now_fn())

    @staticmethod
    def _price(s: str) -> int | None:
        m = re.search(r"([\d.,]+)\s*([kK])?", s)
        if not m:
            return None
        value = float(m.group(1).replace(",", ""))
        return round(value * 1000) if m.group(2) else round(value)

    @classmethod
    def _age(cls, s: str) -> timedelta:
        s = s.lower()
        if s == "today":
            return timedelta(0)
        if s == "yesterday":
            return timedelta(days=1)
        m = re.match(r"(\d+|an?) (\w+?)s? ago", s)
        n = 1 if m.group(1) in ("a", "an") else int(m.group(1))
        return n * cls._UNITS[m.group(2)]

    @classmethod
    def parse(cls, html: str, now: datetime) -> list[Vacancy]:
        starts = [m.start() for m in cls._CARD.finditer(html)]
        out = []
        for a, b in zip(starts, starts[1:] + [len(html)]):
            card = html[a:b]
            try:
                link = cls._LINK.search(card)
                if not link:
                    continue
                url, title = link.group(1), strip_html(link.group(2))
                desc = cls._DESC.search(card)
                price = cls._PRICE.search(card)
                age = cls._AGE.search(card)
                out.append(Vacancy(
                    source="pph", external_id=url.rstrip("/").rsplit("-", 1)[-1], url=url,
                    title=title, company="",
                    published_at=now - (cls._age(age.group(1)) if age else timedelta(0)),
                    kind="freelance", remote=True,
                    salary_to=cls._price(price.group(1)) if price else None,
                    currency="USD" if price else None,
                    description=strip_html(desc.group(1))[:3500] if desc else ""))
            except _ITEM_ERRORS as e:
                log.warning("pph: skip malformed card: %r", e)
        return out


class RemotiveSource(Source):
    name = "remotive"
    URL = "https://remotive.com/api/remote-jobs"
    TYPES = ("freelance", "contract")

    def __init__(self, query: str):
        self.query = query

    async def fetch(self, http: Http) -> list[Vacancy]:
        return self.parse(await http.get_json(self.URL, {"search": self.query, "limit": 100}))

    @classmethod
    def parse(cls, data: dict) -> list[Vacancy]:
        out = []
        for j in data.get("jobs", []):
            if j.get("job_type") not in cls.TYPES:
                continue
            try:
                out.append(Vacancy(
                    source="remotive", external_id=str(j["id"]), url=j["url"],
                    title=strip_html(j["title"]), company=strip_html(j.get("company_name")),
                    published_at=_parse_iso_utc(j["publication_date"]),
                    kind="freelance", remote=True,
                    description=f"Тип: {j['job_type']}. "
                                f"Локация: {j.get('candidate_required_location') or '—'}. "
                                f"Зарплата: {j.get('salary') or '—'}. "
                                + strip_html(j.get("description"))[:3000]))
            except _ITEM_ERRORS as e:
                log.warning("remotive: skip malformed job: %r", e)
        return out


class JobicySource(Source):
    name = "jobicy"
    URL = "https://jobicy.com/api/v2/remote-jobs"

    def __init__(self, tag: str):
        self.tag = tag

    async def fetch(self, http: Http) -> list[Vacancy]:
        return self.parse(await http.get_json(self.URL, {"count": 50, "tag": self.tag}))

    @staticmethod
    def parse(data: dict) -> list[Vacancy]:
        out = []
        for j in data.get("jobs", []):
            if "Contract" not in (j.get("jobType") or []):
                continue
            try:
                out.append(Vacancy(
                    source="jobicy", external_id=str(j["id"]), url=j["url"],
                    title=strip_html(j["jobTitle"]), company=strip_html(j.get("companyName")),
                    published_at=_parse_iso_utc(j["pubDate"]),
                    kind="freelance", remote=True,
                    description=f"Тип: contract. Локация: {j.get('jobGeo') or '—'}. "
                                + strip_html(j.get("jobExcerpt") or j.get("jobDescription"))[:3000]))
            except _ITEM_ERRORS as e:
                log.warning("jobicy: skip malformed job: %r", e)
        return out
