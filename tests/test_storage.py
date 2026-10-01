from datetime import datetime, timedelta, timezone

import pytest

from models import ScoreResult, Vacancy
from storage import Storage

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


def vac(ext="1", source="hh", title="Python dev", company="Acme", **kw):
    return Vacancy(source=source, external_id=ext, url=f"https://x/{ext}", title=title,
                   company=company, published_at=NOW, **kw)


@pytest.fixture
def st(tmp_path):
    return Storage(str(tmp_path / "t.db"))


def test_add_returns_id_and_rejects_same_external_id(st):
    assert st.add(vac("1"), NOW) is not None
    assert st.add(vac("1"), NOW) is None


def test_cross_source_duplicate_within_14_days_rejected(st):
    st.add(vac("1", source="hh", title="Python-разработчик", company="Ромашка"), NOW)
    dup = vac("777", source="telegram", title="python разработчик", company="ромашка")
    assert st.add(dup, NOW + timedelta(days=3)) is None
    assert st.add(dup, NOW + timedelta(days=15)) is not None


def test_dedup_by_description_when_company_empty(st):
    a = vac("a", company="", title="Парсинг сайта",
           description="Нужен парсер сайта конкурентов на Python")
    b = vac("b", company="", title="Парсинг сайта",
           description="Собрать данные о ценах с маркетплейса")
    assert st.add(a, NOW) is not None
    assert st.add(b, NOW) is not None
    c = vac("c", company="", title="Парсинг сайта", description=a.description)
    assert st.add(c, NOW) is None


def test_roundtrip_vacancy(st):
    v = vac("5", remote=True, salary_from=100, salary_to=200, currency="RUB", kind="freelance",
            description="desc")
    row = st.get(st.add(v, NOW))
    assert Storage.row_to_vacancy(row) == v


def test_score_and_send_flow(st):
    a = st.add(vac("a", title="A"), NOW)
    b = st.add(vac("b", title="B"), NOW)
    c = st.add(vac("c", title="C"), NOW)
    assert [r["id"] for r in st.pending(10)] == [a, b, c]
    st.set_score(a, ScoreResult(90, "ok", ["x"], "150k"))
    st.set_score(b, ScoreResult(40, "meh", [], ""))
    st.set_score(c, ScoreResult(None, "не оценено", [], ""))
    assert [r["id"] for r in st.to_send(65, 10)] == [a, c]
    assert st.get(a)["red_flags"] == '["x"]'
    st.mark_sent(a, 555)
    assert st.get(a)["status"] == "sent" and st.get(a)["tg_message_id"] == 555
    assert [r["id"] for r in st.below_threshold(65, 10)] == [b]
    assert [r["id"] for r in st.top(NOW - timedelta(days=1), 10)] == [a, b]


def test_filtered_status_on_add(st):
    i = st.add(vac("f"), NOW, status="filtered")
    assert st.get(i)["status"] == "filtered"
    assert st.pending(10) == []


def test_starred_and_stats(st):
    a = st.add(vac("a", title="A"), NOW)
    st.add(vac("b", title="B"), NOW, status="filtered")
    st.set_status(a, "starred")
    assert [r["id"] for r in st.starred()] == [a]
    assert st.stats(NOW - timedelta(hours=1)) == {"hh": {"collected": 2, "passed": 1, "sent": 1}}


def test_source_state(st):
    s = st.source_state("hh")
    assert s.last_success_at is None and s.consecutive_failures == 0 and not s.alerted
    assert st.record_failure("hh") == 1
    assert st.record_failure("hh") == 2
    st.mark_alerted("hh")
    assert st.source_state("hh").alerted
    st.record_success("hh", NOW)
    s = st.source_state("hh")
    assert s.last_success_at == NOW and s.consecutive_failures == 0 and not s.alerted


def test_settings(st):
    assert st.get_setting("paused", "0") == "0"
    st.set_setting("paused", "1")
    assert st.get_setting("paused") == "1"
