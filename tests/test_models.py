from datetime import datetime, timezone

from models import Vacancy, dedup_hash


def test_dedup_hash_ignores_case_punctuation_and_spaces():
    a = dedup_hash("Python-разработчик (боты)", "ООО «Ромашка»")
    b = dedup_hash("  python разработчик  боты ", "ооо ромашка")
    assert a == b


def test_dedup_hash_differs_for_different_company():
    assert dedup_hash("Python dev", "A") != dedup_hash("Python dev", "B")


def test_dedup_hash_uses_description_when_company_empty():
    a = dedup_hash("Парсинг сайта", "", description="Нужен парсер на Python для сайта X")
    b = dedup_hash("Парсинг сайта", "", description="Совсем другое описание задачи Y")
    assert a != b
    c = dedup_hash("Парсинг сайта", "", description="Нужен парсер на Python для сайта X")
    assert a == c


def test_vacancy_defaults():
    v = Vacancy(source="hh", external_id="1", url="u", title="t", company="c",
                published_at=datetime(2026, 9, 25, tzinfo=timezone.utc))
    assert v.kind == "job"
    assert v.remote is None
    assert v.salary_from is None and v.salary_to is None and v.currency is None
    assert v.description == ""
