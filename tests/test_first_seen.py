"""`first_seen`: when a listing was first observed, carried between runs.

It is not scraped. No source publishes it, so it is derived: a link already in
yesterday's CSV keeps the date it had, and a link never seen before takes
today's. That makes `csv_out` its owner rather than the scraper.
"""

from bendrentals.csv_out import carry_first_seen
from bendrentals.models import UNKNOWN, Listing


def row(link, first_seen=UNKNOWN, **kw):
    base = dict.fromkeys(Listing.fieldnames(), UNKNOWN)
    base.update(link=link, first_seen=first_seen, **kw)
    return base


def test_the_column_exists_and_is_last():
    """Last because it is derived rather than scraped, like the page shows it."""
    assert Listing.fieldnames()[-1] == "first_seen"


def test_a_link_never_seen_before_takes_todays_date():
    fresh = [row("L1")]
    carry_first_seen(fresh, [], today="2026-10-14")
    assert fresh[0]["first_seen"] == "2026-10-14"


def test_a_link_already_in_the_file_keeps_its_date():
    fresh = [row("L1")]
    existing = [row("L1", first_seen="2026-09-03")]
    carry_first_seen(fresh, existing, today="2026-10-14")
    assert fresh[0]["first_seen"] == "2026-09-03"


def test_a_known_link_with_no_date_stays_unknown():
    """It is not new, so dating it today would be a lie.

    This is the pre-backfill state: the row predates the column. The backfill
    fills it from git history; claiming today would make a six-week-old
    listing look like it appeared this morning, and no later run could undo
    that.
    """
    fresh = [row("L1")]
    existing = [row("L1", first_seen=UNKNOWN)]
    carry_first_seen(fresh, existing, today="2026-10-14")
    assert fresh[0]["first_seen"] == UNKNOWN


def test_a_listing_that_returns_under_the_same_link_keeps_its_first_date():
    """Documented as a known edge: two vacancies, one date."""
    fresh = [row("L1")]
    existing = [row("L1", first_seen="2026-09-03")]
    carry_first_seen(fresh, existing, today="2026-10-14")
    assert fresh[0]["first_seen"] == "2026-09-03"


def test_an_already_dated_fresh_row_is_not_overwritten():
    """The backfill writes dates straight onto rows; a later run must keep them."""
    fresh = [row("L1", first_seen="2026-09-10")]
    carry_first_seen(fresh, [], today="2026-10-14")
    assert fresh[0]["first_seen"] == "2026-09-10"


def test_rows_without_a_link_are_left_alone():
    fresh = [row("")]
    carry_first_seen(fresh, [], today="2026-10-14")
    assert fresh[0]["first_seen"] == UNKNOWN


def test_it_returns_how_many_were_newly_dated():
    fresh = [row("L1"), row("L2"), row("L3", first_seen="2026-01-01")]
    existing = [row("L1", first_seen="2026-09-03")]
    assert carry_first_seen(fresh, existing, today="2026-10-14") == 1
