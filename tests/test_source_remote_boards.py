import json
from datetime import datetime, timezone
from pathlib import Path

from sources.remote_boards import HimalayasSource, RemoteOkSource, WwrSource


def text(name):
    return Path(f"tests/fixtures/{name}").read_text(encoding="utf-8")


def test_remoteok_skips_legal_and_non_python():
    items = RemoteOkSource.parse(json.loads(text("remoteok.json")))
    assert len(items) == 1
    v = items[0]
    assert v.source == "remoteok" and v.external_id == "1137394"
    assert v.title == "Sr Solutions Architect" and v.company == "ExtraHop"
    assert v.url == "https://remoteOK.com/remote-jobs/remote-sr-solutions-architect-extrahop-1137394"
    assert v.remote is True
    assert v.salary_from is None and v.salary_to is None
    assert v.published_at == datetime(2026, 9, 15, 0, 0, 26, tzinfo=timezone.utc)


def test_remoteok_yearly_salary_to_monthly():
    data = json.loads(text("remoteok.json"))
    data[1]["salary_min"], data[1]["salary_max"] = 60000, 120000
    v = RemoteOkSource.parse(data)[0]
    assert (v.salary_from, v.salary_to, v.currency) == (5000, 10000, "USD")


def test_wwr():
    items = WwrSource.parse(text("wwr.rss"))
    assert len(items) == 2
    v = items[0]
    assert v.source == "wwr"
    assert v.external_id == v.url == "https://weworkremotely.com/remote-jobs/twikey-java-developer"
    assert v.title == "Java Developer" and v.company == "Twikey"
    assert v.published_at == datetime(2026, 9, 17, 10, 51, 23, tzinfo=timezone.utc)
    assert "Java, PostgreSQL" in v.description
    assert "<p>" not in v.description


def test_himalayas():
    items = HimalayasSource.parse(json.loads(text("himalayas.json")))
    assert len(items) == 2
    v = items[0]
    assert v.source == "himalayas"
    assert v.external_id == "https://himalayas.app/companies/lemon-io/jobs/senior-react-native-developer-5236230554"
    assert v.url == v.external_id
    assert v.title == "Senior React Native Developer" and v.company == "lemon.io"
    assert v.published_at == datetime.fromtimestamp(1789127040, tz=timezone.utc)
    assert v.salary_from is None
    assert v.remote is True
