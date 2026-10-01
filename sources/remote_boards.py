import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from httpclient import Http
from models import Vacancy
from sources.base import Source
from textutil import strip_html

log = logging.getLogger("job_hunter")


def _fix_mojibake(s: str) -> str:
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _monthly(yearly) -> int | None:
    return round(yearly / 12) if yearly else None


class RemoteOkSource(Source):
    name = "remoteok"
    URL = "https://remoteok.com/api"

    async def fetch(self, http: Http) -> list[Vacancy]:
        return self.parse(await http.get_json(self.URL))

    @staticmethod
    def parse(data: list) -> list[Vacancy]:
        out = []
        for x in data:
            if "id" not in x or "python" not in [t.lower() for t in x.get("tags") or []]:
                continue
            try:
                lo, hi = _monthly(x.get("salary_min")), _monthly(x.get("salary_max"))
                out.append(Vacancy(
                    source="remoteok", external_id=str(x["id"]), url=x["url"],
                    title=_fix_mojibake(x["position"]).strip(),
                    company=_fix_mojibake(x.get("company", "")),
                    published_at=datetime.fromisoformat(x["date"]).astimezone(timezone.utc),
                    remote=True, salary_from=lo, salary_to=hi, currency="USD" if lo or hi else None,
                    description=f"Tags: {', '.join(x.get('tags') or [])}. "
                                + strip_html(x.get("description"))[:3000]))
            except (KeyError, TypeError, ValueError, AttributeError):
                log.warning("remoteok: skipping malformed item", exc_info=True)
        return out


class WwrSource(Source):
    name = "wwr"
    URL = "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss"

    async def fetch(self, http: Http) -> list[Vacancy]:
        return self.parse(await http.get_text(self.URL))

    @staticmethod
    def parse(xml: str) -> list[Vacancy]:
        out = []
        for it in ET.fromstring(xml).iter("item"):
            try:
                company, _, title = it.findtext("title").partition(": ")
                url = it.findtext("guid").strip()
                out.append(Vacancy(
                    source="wwr", external_id=url, url=url,
                    title=(title or company).strip(), company=company.strip() if title else "",
                    published_at=parsedate_to_datetime(
                        it.findtext("pubDate")).astimezone(timezone.utc),
                    remote=True,
                    description=f"Skills: {it.findtext('skills') or ''}. "
                                + strip_html(it.findtext("description"))[:3000]))
            except (KeyError, TypeError, ValueError, AttributeError):
                log.warning("wwr: skipping malformed item", exc_info=True)
        return out


class HimalayasSource(Source):
    name = "himalayas"
    URL = "https://himalayas.app/jobs/api/search"

    def __init__(self, query: str):
        self.query = query

    async def fetch(self, http: Http) -> list[Vacancy]:
        return self.parse(await http.get_json(self.URL, {"q": self.query, "limit": 50}))

    @staticmethod
    def parse(data: dict) -> list[Vacancy]:
        out = []
        for j in data.get("jobs", []):
            try:
                lo, hi = _monthly(j.get("minSalary")), _monthly(j.get("maxSalary"))
                where = ", ".join(j.get("locationRestrictions") or []) or "Worldwide"
                out.append(Vacancy(
                    source="himalayas", external_id=j["guid"], url=j["guid"],
                    title=j["title"].strip(), company=j.get("companyName", ""),
                    published_at=datetime.fromtimestamp(j["pubDate"], tz=timezone.utc),
                    remote=True, salary_from=lo, salary_to=hi,
                    currency=j.get("currency") if lo or hi else None,
                    description=f"Locations: {where[:300]}. {j.get('excerpt') or ''}"))
            except (KeyError, TypeError, ValueError, AttributeError):
                log.warning("himalayas: skipping malformed item", exc_info=True)
        return out
