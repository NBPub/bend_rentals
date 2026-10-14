import pytest

from bendrentals.cli import FlagError, flag_value


def test_reads_the_separate_form():
    assert flag_value(["--days", "14"], "--days") == "14"


def test_reads_the_equals_form():
    """Silently ignoring this read `--days=14` as the default."""
    assert flag_value(["--days=14"], "--days") == "14"


def test_an_absent_flag_gives_the_fallback():
    assert flag_value(["--other", "x"], "--days", "7") == "7"


def test_a_flag_with_nothing_after_it_is_an_error():
    """Falling back here answers a different question without saying so."""
    with pytest.raises(FlagError, match="needs a value"):
        flag_value(["--out", "x", "--days"], "--days")


def test_an_empty_equals_value_is_an_error():
    with pytest.raises(FlagError, match="needs a value"):
        flag_value(["--days="], "--days")


def test_the_first_occurrence_wins():
    assert flag_value(["--days", "3", "--days", "9"], "--days") == "3"


def test_a_value_that_looks_like_a_flag_is_still_the_value():
    """So a typo is visible downstream rather than silently defaulted."""
    assert flag_value(["--out", "--days"], "--out") == "--days"


def test_a_longer_flag_sharing_a_prefix_is_not_confused():
    assert flag_value(["--csv-url", "http://x"], "--csv", "fallback") == "fallback"
