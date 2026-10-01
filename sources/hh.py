import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from httpclient import Http
from models import Vacancy
from sources.base import Source
from textutil import parse_salary, strip_html

URL = "https://hh.ru/search/vacancy/rss"
_COMPANY = re.compile(r"Вакансия компании:\s*(.+?)\s+Создана:")
log = logging.getLogger("job_hunter")


class HhSource(Source):
    name = "hh"

    def __init__(self, query: str):
        self.query = query

    async def fetch(self, http: Http) -> list[Vacancy]:
        xml = await http.get_text(URL, {"text": self.query, "work_format": "REMOTE",
                                        "search_field": "name"})
        return self.parse(xml)

    @staticmethod
    def parse(xml: str) -> list[Vacancy]:
        out = []
        for it in ET.fromstring(xml).iter("item"):
            try:
                url = it.findtext("link").strip()
                desc = strip_html(it.findtext("description"))
                m = _COMPANY.search(desc)
                s_from, s_to, cur = parse_salary(desc)
                out.append(Vacancy(
                    source="hh", external_id=url.rstrip("/").rsplit("/", 1)[-1], url=url,
                    title=it.findtext("title").strip(), company=m.group(1) if m else "",
                    published_at=datetime.fromisoformat(it.findtext("pubDate")).astimezone(timezone.utc),
                    remote=True, salary_from=s_from, salary_to=s_to, currency=cur,
                    description=desc))
            except (KeyError, TypeError, ValueError, AttributeError):
                log.warning("hh: skipping malformed item", exc_info=True)
        return out
