from bendrentals.changelog import (
    STALE_DAYS, companies_behind, geocode_flags, run_date, source_status,
)


def row(company="A", link="L1", scraped="2026-01-10T08:00:00", lat="44.0", **kw):
    base = {"company": company, "link": link, "scraped_at": scraped,
            "lat": lat, "address": "1 Main St", "price": "1000"}
    base.update(kw)
    return base


def test_run_date_is_the_newest_stamp_in_the_file():
    rows = [row(scraped="2026-01-09T08:00:00"), row(scraped="2026-01-10T08:00:00")]
    assert run_date(rows) == "2026-01-10"


def test_run_date_ignores_unparseable_stamps():
    """Review Focus 1: a partial parse can leave scraped_at unstamped."""
    assert run_date([row(scraped="?"), row(scraped="2026-01-10T08:00:00")]) \
        == "2026-01-10"


def test_run_date_of_an_empty_file_is_empty():
    assert run_date([]) == ""


def test_source_status_takes_each_companys_newest_stamp():
    rows = [row(company="A", link="1", scraped="2026-01-08T08:00:00"),
            row(company="A", link="2", scraped="2026-01-10T08:00:00"),
            row(company="B", link="3", scraped="2026-01-07T08:00:00")]
    assert source_status(rows) == {"A": "2026-01-10", "B": "2026-01-07"}


def test_a_company_that_refreshed_today_is_not_behind():
    status = {"A": "2026-01-10"}
    assert companies_behind(status, today="2026-01-10") == {}


def test_a_company_that_missed_today_is_behind_by_a_day():
    status = {"A": "2026-01-09"}
    assert companies_behind(status, today="2026-01-10") == {"A": 1}


def test_the_stale_threshold_is_inclusive():
    status = {"exactly": "2026-01-07", "under": "2026-01-08"}
    behind = companies_behind(status, today="2026-01-10", threshold=STALE_DAYS)
    assert behind == {"exactly": 3}


def test_an_unparseable_stamp_is_skipped_not_crashed():
    """Review Focus 1: date.fromisoformat raises on '?'."""
    status = {"bad": "?", "good": "2026-01-05"}
    assert companies_behind(status, today="2026-01-10") == {"good": 5}


def test_geocode_flags_lists_unmapped_rows():
    rows = [row(link="1", lat="44.0"),
            row(link="2", lat="?", company="B", address="Nowhere")]
    flags = geocode_flags(rows, {})
    assert [u["address"] for u in flags["unmapped"]] == ["Nowhere"]
    assert flags["unmapped"][0]["company"] == "B"


def test_geocode_flags_counts_cached_failures_and_the_next_retry():
    entries = {
        "a": {"lat": "44.0", "lon": "-121.0"},
        "b": {"lat": "?", "lon": "?", "failed_at": "2026-01-05"},
        "c": {"lat": "?", "lon": "?", "failed_at": "2026-01-08"},
        "d": {"lat": "?", "lon": "?"},
    }
    flags = geocode_flags([], entries)
    assert flags["failures"] == 3
    assert flags["undated_failures"] == 1
    assert flags["next_retry"] == "2026-02-04"   # 2026-01-05 + 30 days
