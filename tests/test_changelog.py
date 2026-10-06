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


from bendrentals.changelog import build


def rows_by_link(*rows):
    return {r["link"]: r for r in rows}


TODAY = "2026-01-10"
CURRENT = [row(link="L2", scraped=f"{TODAY}T08:00:00")]


def test_a_day_with_no_changes_says_so_and_has_no_table():
    same = rows_by_link(row(link="L1"))
    text = build([("2026-01-09", same), (TODAY, same)], CURRENT, {})
    assert "No listings added or removed" in text
    assert "| Company | Added | Removed |" not in text


def test_a_day_reports_counts_and_names_the_listings():
    before = rows_by_link(row(link="L1", address="Gone St"))
    after = rows_by_link(row(link="L2", address="New Ave"))
    text = build([("2026-01-09", before), (TODAY, after)], CURRENT, {})
    assert "| A | 1 | 1 |" in text
    assert "New Ave" in text and "Gone St" in text
    assert "<details>" in text


def test_days_are_newest_first():
    d1 = rows_by_link(row(link="L1"))
    d2 = rows_by_link(row(link="L1"), row(link="L2"))
    d3 = rows_by_link(row(link="L2"))
    text = build([("2026-01-08", d1), ("2026-01-09", d2), (TODAY, d3)],
                 CURRENT, {})
    assert text.index(f"### {TODAY}") < text.index("### 2026-01-09")


def test_a_pipe_in_a_company_label_does_not_break_the_table():
    """Review Focus 3: one pipe would split the row into nonsense."""
    before = rows_by_link(row(company="Pipe|Co", link="L1"))
    after = {}
    text = build([("2026-01-09", before), (TODAY, after)], CURRENT, {})
    table_line = next(l for l in text.splitlines()
                      if "Pipe" in l and l.startswith("|"))
    # Escaped pipes are literal text, not cell delimiters, so discount them
    # before counting: four delimiters means three cells, as the header has.
    assert table_line.replace(r"\|", "").count("|") == 4
    assert r"Pipe\|Co" in table_line


def test_a_schema_change_does_not_invent_added_or_removed_listings():
    """Review Focus 4: the old CSV lacks a column the new one has."""
    before = {"L1": {"company": "A", "link": "L1", "address": "Same St"}}
    after = {"L1": {"company": "A", "link": "L1", "address": "Same St",
                    "dogs_allowed": "True"}}
    text = build([("2026-01-09", before), (TODAY, after)], CURRENT, {})
    assert "No listings added or removed" in text


def test_all_sources_current_says_so_in_one_line():
    text = build([], CURRENT, {})
    assert "All sources refreshed" in text


def test_a_source_that_missed_today_is_named():
    current = [row(company="A", link="1", scraped=f"{TODAY}T08:00:00"),
               row(company="B", link="2", scraped="2026-01-08T08:00:00")]
    text = build([], current, {})
    assert "B" in text.split("## Sources")[1].split("##")[0]


def test_stale_listings_are_named_past_the_threshold():
    current = [row(company="A", link="1", scraped=f"{TODAY}T08:00:00"),
               row(company="Old", link="2", scraped="2026-01-05T08:00:00",
                   address="Stale Rd")]
    text = build([], current, {})
    stale = text.split("## Stale listings")[1]
    assert "Stale Rd" in stale


def test_nothing_stale_says_so():
    text = build([], CURRENT, {})
    assert "No stale listings" in text


def test_geocoding_with_nothing_to_report_says_nothing_to_flag():
    text = build([], CURRENT, {})
    assert "Nothing to flag" in text.split("## Geocoding")[1].split("##")[0]


def test_history_unavailable_is_stated_not_hidden():
    text = build([], CURRENT, {}, history_error="shallow clone")
    assert "shallow clone" in text
    assert "## Sources" in text          # the rest of the file is still built


def test_too_little_history_is_not_an_error():
    only_today = [(TODAY, rows_by_link(row(link="L2")))]
    text = build(only_today, CURRENT, {})
    assert "Not enough history yet" in text


def test_building_twice_gives_identical_text():
    """The file is committed, so it must not churn."""
    args = ([("2026-01-09", rows_by_link(row(link="L1"))),
             (TODAY, rows_by_link(row(link="L2")))], CURRENT, {})
    assert build(*args) == build(*args)


def test_labels_shorten_company_names():
    before = rows_by_link(row(company="A Very Long Name", link="L1"))
    text = build([("2026-01-09", before), (TODAY, {})], CURRENT,
                 {}, labels={"A Very Long Name": "Short"})
    assert "| Short | 0 | 1 |" in text
    assert "A Very Long Name" not in text


def test_geocoding_uses_the_short_label_like_every_other_table():
    """One company must not appear under two names in the same file."""
    current = [row(company="A Very Long Name", link="L1", lat="?",
                   address="Unmapped Rd", scraped=f"{TODAY}T08:00:00")]
    text = build([], current, {}, labels={"A Very Long Name": "Short"})
    geocoding = text.split("## Geocoding")[1].split("## Stale")[0]
    assert "| Short | Unmapped Rd |" in geocoding
    assert "A Very Long Name" not in geocoding


def test_the_geocoding_table_is_sorted_by_what_it_displays():
    """Sorting by the hidden full name makes the visible order look arbitrary."""
    current = [row(company="Zeta Holdings", link="L1", lat="?",
                   address="Zed Rd", scraped=f"{TODAY}T08:00:00"),
               row(company="Alpha Group", link="L2", lat="?",
                   address="Alpha Rd", scraped=f"{TODAY}T08:00:00")]
    # Labels invert the alphabetical order of the full names.
    text = build([], current, {},
                 labels={"Zeta Holdings": "Aaa", "Alpha Group": "Zzz"})
    geocoding = text.split("## Geocoding")[1].split("## Stale")[0]
    assert geocoding.index("| Aaa |") < geocoding.index("| Zzz |")


def test_an_unreadable_revision_labels_its_day_rather_than_merging_two():
    """A skipped revision must not silently attribute two days to one date.

    Dropping it from the list would leave two non-adjacent revisions side by
    side, headed with the later date only.
    """
    d1 = rows_by_link(row(link="L1"))
    d3 = rows_by_link(row(link="L3"))
    text = build([("2026-01-08", d1), ("2026-01-09", None), (TODAY, d3)],
                 CURRENT, {})
    assert "No comparison available" in text
    # The day whose predecessor is missing gets no invented count table.
    today_section = text.split(f"### {TODAY}")[1].split("##")[0]
    assert "| Company | Added | Removed |" not in today_section
