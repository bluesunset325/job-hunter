import logging
from datetime import datetime, timezone

from httpclient import Http
from models import Vacancy
from sources.base import Source
from textutil import strip_html

URL = "https://getmatch.ru/api/offers"
log = logging.getLogger("job_hunter")


class GetMatchSource(Source):
    name = "getmatch"

    async def fetch(self, http: Http) -> list[Vacancy]:
        data = await http.get_json(URL, {"pa": "all", "sp": "python", "l": "remote",
                                         "offset": 0, "limit": 50})
        return self.parse(data)

    @staticmethod
    def parse(data: dict) -> list[Vacancy]:
        out = []
        for o in data.get("offers", []):
            try:
                published = datetime.fromisoformat(o["published_at"])
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                hidden = o.get("salary_hidden")
                out.append(Vacancy(
                    source="getmatch", external_id=str(o["id"]),
                    url=f"https://getmatch.ru{o['url']}", title=o["position"].strip(),
                    company=(o.get("company") or {}).get("name", ""),
                    published_at=published.astimezone(timezone.utc),
                    remote=any(l.get("format") == "remote"
                              for l in o.get("location_requirements") or []),
                    salary_from=None if hidden else o.get("salary_display_from"),
                    salary_to=None if hidden else o.get("salary_display_to"),
                    currency=None if hidden else o.get("salary_currency"),
                    description=strip_html(o.get("offer_description"))))
            except (KeyError, TypeError, ValueError, AttributeError):
                log.warning("getmatch: skipping malformed item", exc_info=True)
        return out
