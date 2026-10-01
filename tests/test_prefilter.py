from datetime import datetime, timezone

from config import SearchCfg
from models import Vacancy
from prefilter import keep

S = SearchCfg(query="python", keywords=["python", "aiogram"], stop_words=["1с", "офис"],
              min_salary_rub=80000)
R = {"RUB": 1.0, "USD": 82.0}


def v(title="Python developer", description="", **kw):
    return Vacancy(source="hh", external_id="1", url="u", title=title, company="c",
                   published_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
                   description=description, **kw)


def test_keeps_matching():
    assert keep(v(), S, R)


def test_drops_without_keyword():
    assert not keep(v(title="Java developer"), S, R)


def test_keyword_in_description_is_enough():
    assert keep(v(title="Backend", description="Стек: Aiogram, Postgres"), S, R)


def test_drops_stop_word():
    assert not keep(v(title="Python + 1С программист"), S, R)


def test_drops_not_remote_but_keeps_unknown():
    assert not keep(v(remote=False), S, R)
    assert keep(v(remote=None), S, R)


def test_salary_below_min_dropped_with_conversion():
    assert not keep(v(salary_to=60000, currency="RUB"), S, R)
    assert keep(v(salary_from=1500, currency="USD"), S, R)      # 123 000 ₽
    assert not keep(v(salary_from=500, currency="USD"), S, R)   # 41 000 ₽


def test_unknown_currency_or_no_salary_kept():
    assert keep(v(salary_to=10, currency="KZT"), S, R)
    assert keep(v(), S, R)


def test_freelance_ignores_salary():
    assert keep(v(kind="freelance", salary_to=1500, currency="RUB"), S, R)


BOT_S = SearchCfg(query="python", keywords=["бот"], stop_words=["lead", "senior+"],
                  min_salary_rub=80000)


def test_keyword_substring_inside_unrelated_word_does_not_match():
    assert not keep(v(title="Разработчик C++", description=""), BOT_S, R)


def test_keyword_matches_at_word_start_of_derived_word():
    assert keep(v(title="Telegram-бота на aiogram", description=""), BOT_S, R)


def test_stop_word_whole_word_does_not_match_inside_longer_word():
    assert keep(v(title="Telegram-бот developer", description="leadership skills"), BOT_S, R)


def test_stop_word_regex_special_chars_are_escaped():
    assert not keep(v(title="Python бот senior+ developer", description=""), BOT_S, R)


def test_currency_compared_case_insensitively():
    assert not keep(v(salary_to=60000, currency="rub"), S, R)


S_FL = SearchCfg(query="python", keywords=["python"], stop_words=[], min_salary_rub=80000,
                 min_freelance_usd=50)
R_FL = {"RUB": 1.0, "USD": 82.0, "GBP": 110.0}


def test_foreign_freelance_below_min_budget_dropped():
    assert not keep(v(kind="freelance", salary_to=30, currency="USD"), S_FL, R_FL)
    assert keep(v(kind="freelance", salary_to=130, currency="USD"), S_FL, R_FL)
    assert keep(v(kind="freelance", salary_to=40, currency="GBP"), S_FL, R_FL)  # ≈ $54


def test_min_freelance_budget_ignores_rub():
    assert keep(v(kind="freelance", salary_to=1500, currency="RUB"), S_FL, R_FL)


def test_cheap_hourly_dropped():
    assert not keep(v(kind="freelance", salary_from=2, salary_to=8, currency="USD/h"), S_FL, R_FL)
    assert keep(v(kind="freelance", salary_from=15, salary_to=30, currency="USD/h"), S_FL, R_FL)
