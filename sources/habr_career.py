import logging
from datetime import datetime, timezone

from httpclient import Http
from models import Vacancy
from sources.base import Source

URL = "https://career.habr.com/api/frontend/vacancies"
_CUR = {"rur": "RUB", "rub": "RUB", "usd": "USD", "eur": "EUR"}
log = logging.getLogger("job_hunter")


class HabrCareerSource(Source):
    name = "habr_career"

    def __init__(self, query: str):
        self.query = query

    async def fetch(self, http: Http) -> list[Vacancy]:
        data = await http.get_json(URL, {"q": self.query, "remote": "true", "type": "all",
                                         "sort": "date"})
        return self.parse(data)

    @staticmethod
    def parse(data: dict) -> list[Vacancy]:
        out = []
        for x in data.get("list", []):
            try:
                salary = x.get("salary") or {}
                skills = ", ".join(s["title"] for s in x.get("skills") or [])
                desc = f"Навыки: {skills}" + (f"; {x['qualification']}" if x.get("qualification") else "")
                out.append(Vacancy(
                    source="habr_career", external_id=str(x["id"]),
                    url=f"https://career.habr.com{x['href']}", title=x["title"].strip(),
                    company=(x.get("company") or {}).get("title", ""),
                    published_at=datetime.fromisoformat(
                        x["publishedDate"]["date"]).astimezone(timezone.utc),
                    remote=bool(x.get("remoteWork")),
                    salary_from=salary.get("from"), salary_to=salary.get("to"),
                    currency=_CUR.get((salary.get("currency") or "").lower()),
                    description=desc))
            except (KeyError, TypeError, ValueError, AttributeError):
                log.warning("habr_career: skipping malformed item", exc_info=True)
        return out
