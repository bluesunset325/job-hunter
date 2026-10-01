from httpclient import Http
from models import Vacancy


class Source:
    name: str = ""

    async def fetch(self, http: Http) -> list[Vacancy]:
        raise NotImplementedError
