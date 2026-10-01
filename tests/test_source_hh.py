from datetime import datetime, timezone
from pathlib import Path

from sources.hh import HhSource

XML = Path("tests/fixtures/hh.rss").read_text(encoding="utf-8")


def test_parse_hh_rss():
    items = HhSource.parse(XML)
    assert len(items) == 2
    a, b = items
    assert a.source == "hh" and a.external_id == "134564796"
    assert a.url == "https://hh.ru/vacancy/134564796"
    assert a.title == "Middle+ Python developer"
    assert a.company == "Циан"
    assert a.remote is True and a.kind == "job"
    assert a.salary_from is None and a.salary_to is None
    assert a.published_at == datetime(2026, 9, 23, 8, 17, 29, 289000, tzinfo=timezone.utc)
    assert "Регион: Москва" in a.description
    assert b.company == "Вельц Станислав Сергеевич"
    assert (b.salary_from, b.salary_to, b.currency) == (None, 120000, "RUB")


def test_item_missing_link_is_skipped_others_still_parsed():
    bad_xml = XML.replace(
        "<link>https://hh.ru/vacancy/134564796</link>", "")
    items = HhSource.parse(bad_xml)
    assert len(items) == 1
    assert items[0].external_id == "137539010"
