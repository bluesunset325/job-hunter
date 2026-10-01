import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from httpclient import Http
from models import Vacancy
from sources.base import Source
from textutil import parse_salary, strip_html

MSK = ZoneInfo("Europe/Moscow")
_STATE = "window.stateData="
log = logging.getLogger("job_hunter")


class KworkSource(Source):
    name = "kwork"
    URL = "https://kwork.ru/projects"

    async def fetch(self, http: Http) -> list[Vacancy]:
        return self.parse(await http.get_text(self.URL, {"c": 41}))

    @staticmethod
    def parse(html: str) -> list[Vacancy]:
        i = html.find(_STATE)
        if i < 0:
            return []
        data, _ = json.JSONDecoder().raw_decode(html[i + len(_STATE):])
        out = []
        for w in (data.get("wantsListData") or {}).get("wants", []):
            try:
                created = datetime.strptime(
                    w["date_create"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=MSK)
                out.append(Vacancy(
                    source="kwork", external_id=str(w["id"]),
                    url=f"https://kwork.ru/projects/{w['id']}",
                    title=w["name"].strip(), company="", published_at=created.astimezone(timezone.utc),
                    kind="freelance", remote=True,
                    salary_to=int(float(w["priceLimit"])) if w.get("priceLimit") else None,
                    currency="RUB" if w.get("priceLimit") else None,
                    description=strip_html(w.get("description"))[:4000]))
            except (KeyError, TypeError, ValueError, AttributeError):
                log.warning("kwork: skipping malformed item", exc_info=True)
        return out


class FlSource(Source):
    name = "fl"
    URL = "https://www.fl.ru/rss/all.xml"

    async def fetch(self, http: Http) -> list[Vacancy]:
        return self.parse(await http.get_text(self.URL, {"category": 5}))

    @staticmethod
    def parse(xml: str) -> list[Vacancy]:
        out = []
        for it in ET.fromstring(xml).iter("item"):
            try:
                url = it.findtext("link").strip()
                m = re.search(r"/projects/(\d+)/", url)
                desc = strip_html(it.findtext("description"))
                s_from, s_to, cur = parse_salary(desc)
                out.append(Vacancy(
                    source="fl", external_id=m.group(1) if m else url, url=url,
                    title=it.findtext("title").strip(), company="",
                    published_at=parsedate_to_datetime(
                        it.findtext("pubDate")).astimezone(timezone.utc),
                    kind="freelance", remote=True, salary_from=s_from, salary_to=s_to, currency=cur,
                    description=f"{it.findtext('category') or ''}. {desc}"))
            except (KeyError, TypeError, ValueError, AttributeError):
                log.warning("fl: skipping malformed item", exc_info=True)
        return out
