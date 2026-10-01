import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sources.foreign_freelance import (FreelancerComSource, JobicySource, PphSource,
                                       RemotiveSource)

NOW = datetime(2026, 9, 26, 18, 0, tzinfo=timezone.utc)


def text(name):
    return Path(f"tests/fixtures/{name}").read_text(encoding="utf-8")


def test_freelancer_fixed_usd():
    items = FreelancerComSource.parse(json.loads(text("freelancer.json")))
    assert len(items) == 3
    v = items[0]
    assert v.source == "freelancer" and v.external_id == "40734747"
    assert v.url == "https://www.freelancer.com/projects/natural-language-processing/lisis-Temas-Documentos"
    assert v.title == "Análisis de Temas en Documentos"
    assert v.kind == "freelance" and v.remote is True
    assert (v.salary_from, v.salary_to, v.currency) == (10, 30, "USD")
    assert v.company == "откликов: 24"
    assert v.published_at == datetime.fromtimestamp(1790425980, tz=timezone.utc)
    assert "фиксированная" in v.description


def test_freelancer_converts_currency_to_usd():
    v = FreelancerComSource.parse(json.loads(text("freelancer.json")))[1]
    assert v.title == "Back-End and Data Engineering Support"
    assert (v.salary_from, v.salary_to, v.currency) == (130, 391, "USD")  # 12500/37500 INR


def test_freelancer_hourly_marked_per_hour():
    v = FreelancerComSource.parse(json.loads(text("freelancer.json")))[2]
    assert (v.salary_from, v.salary_to, v.currency) == (2, 8, "USD/h")
    assert "почасовая" in v.description


async def test_freelancer_fetch_merges_queries_without_duplicates():
    data = json.loads(text("freelancer.json"))

    class FakeHttp:
        def __init__(self):
            self.queries = []

        async def get_json(self, url, params=None):
            self.queries.append(params["query"])
            return data

    http = FakeHttp()
    items = await FreelancerComSource(["python", "telegram bot"]).fetch(http)
    assert http.queries == ["python", "telegram bot"]
    assert len(items) == 3


def test_pph():
    items = PphSource.parse(text("pph.html"), NOW)
    assert len(items) == 2
    a, b = items
    assert a.source == "pph" and a.external_id == "4523061"
    assert a.url.startswith("https://www.peopleperhour.com/freelance-jobs/")
    assert a.title == "AI Model Fine-Tuning for Improved Performance and Accuracy"
    assert (a.salary_to, a.currency) == (148, "USD")
    assert a.published_at == NOW - timedelta(days=3)
    assert a.kind == "freelance" and a.remote is True
    assert a.description
    assert b.title == "Crypto Trading Bot" and b.salary_to == 409
    assert b.published_at == NOW - timedelta(days=20)


def test_pph_price_and_age_formats():
    assert PphSource._price("$1.3K") == 1300
    assert PphSource._price("$45") == 45
    assert PphSource._age("2 months ago") == timedelta(days=60)
    assert PphSource._age("5 hours ago") == timedelta(hours=5)
    assert PphSource._age("yesterday") == timedelta(days=1)


def test_remotive_keeps_only_freelance_and_contract():
    items = RemotiveSource.parse(json.loads(text("remotive.json")))
    assert len(items) == 1
    v = items[0]
    assert v.source == "remotive" and v.external_id == "2091140"
    assert v.title == "Senior Shopify Developer" and v.company == "Sanctuary Computer Inc"
    assert v.kind == "freelance" and v.remote is True
    assert v.published_at == datetime(2026, 9, 18, 15, 10, 28, tzinfo=timezone.utc)
    assert "contract" in v.description and "Worldwide" in v.description
    assert "$80k - $150k" in v.description


def test_jobicy_keeps_only_contract():
    items = JobicySource.parse(json.loads(text("jobicy.json")))
    assert len(items) == 1
    v = items[0]
    assert v.source == "jobicy" and v.external_id == "154032"
    assert v.company == "Mozilla" and v.kind == "freelance"
    assert v.published_at == datetime(2026, 9, 24, 15, 33, 8, tzinfo=timezone.utc)
    assert "Canada" in v.description


def test_html_entities_decoded_in_company_and_title():
    data = json.loads(text("jobicy.json"))
    data["jobs"][0]["companyName"] = "Zone &#038; Co"
    data["jobs"][0]["jobTitle"] = "Dev &amp; Ops"
    v = JobicySource.parse(data)[0]
    assert v.company == "Zone & Co" and v.title == "Dev & Ops"
