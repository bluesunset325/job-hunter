import pytest

from textutil import parse_salary, strip_html


@pytest.mark.parametrize("text,expected", [
    ("Предполагаемый уровень месячного дохода: от 80 000 до 150 000 ₽", (80000, 150000, "RUB")),
    ("до 120 000 ₽", (None, 120000, "RUB")),
    ("от 1 750 $", (1750, None, "USD")),
    ("зп 150-200к руб", (150000, 200000, "RUB")),
    ("200 000 – 250 000 руб.", (200000, 250000, "RUB")),
    ("от 3000 до 4000 usd", (3000, 4000, "USD")),
    ("не указан", (None, None, None)),
])
def test_parse_salary(text, expected):
    assert parse_salary(text) == expected


def test_strip_html():
    assert strip_html("<p>a&amp;b</p>\n<p>c</p>") == "a&b c"
    assert strip_html(None) == ""
