import pytest

from bendrentals.dates import parse_available
from bendrentals.models import UNKNOWN


@pytest.mark.parametrize("text,expected", [
    # AppFolio: M/D/YY
    ("9/15/26", "2026-09-15"),
    ("10/15/26", "2026-10-15"),
    ("9/5/26", "2026-09-05"),
    # Buildium: a label plus M/D/YYYY
    ("Available 10/20/2026", "2026-10-20"),
    ("Available 9/1/2026", "2026-09-01"),
    # Rentvine: already ISO
    ("2026-10-01", "2026-10-01"),
    ("2026-08-03", "2026-08-03"),
    # Preferred Residential: month name
    ("August 1, 2026", "2026-08-01"),
    ("Aug 1, 2026", "2026-08-01"),
])
def test_every_source_format_normalises_to_iso(text, expected):
    assert parse_available(text) == (expected, "False")


@pytest.mark.parametrize("text", ["NOW", "now", "Available NOW", "Available Now",
                                  "immediately", "Available immediately"])
def test_immediate_availability_sets_the_flag_and_no_date(text):
    # Writing today's date would invent a fact and churn on every run.
    assert parse_available(text) == (UNKNOWN, "True")


@pytest.mark.parametrize("text", ["", None, UNKNOWN, "   ", "Available", "call us"])
def test_silence_is_unknown_on_both_columns(text):
    # A source saying nothing is not a claim that the place is unavailable.
    assert parse_available(text) == (UNKNOWN, UNKNOWN)


def test_two_digit_years_resolve_to_this_century():
    assert parse_available("1/1/27")[0] == "2027-01-01"
    assert parse_available("12/31/99")[0] == "1999-12-31"


def test_an_impossible_date_is_not_invented():
    # 13 is not a month; better "?" than a wrong date.
    assert parse_available("13/45/26") == (UNKNOWN, UNKNOWN)
    assert parse_available("2026-02-30") == (UNKNOWN, UNKNOWN)


def test_a_date_wins_over_the_word_now():
    # "Available now through 9/15/26" states a real date; prefer it.
    assert parse_available("Available now through 9/15/26") == ("2026-09-15", "False")


def test_day_and_month_are_not_transposed():
    # US ordering: 10/1 is 1 October, not 10 January.
    assert parse_available("10/1/26")[0] == "2026-10-01"
