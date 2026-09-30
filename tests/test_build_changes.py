import csv
from pathlib import Path

import pytest

import build_changes
from bendrentals.geocode import GeocodeCache

FIELDS = ["company", "link", "address", "price", "scraped_at", "lat", "lon"]


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({f: r.get(f, "") for f in FIELDS})


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "listings.csv"
    write_csv(path, [{"company": "A", "link": "https://x/1", "address": "1 Main",
                      "price": "1000", "scraped_at": "2026-01-10T08:00:00",
                      "lat": "44.0", "lon": "-121.0"}])
    return path


def test_it_writes_the_file(tmp_path, csv_file, monkeypatch):
    out = tmp_path / "LISTING_CHANGES.md"
    monkeypatch.setattr(build_changes, "_history", lambda **kw: ([], ""))
    assert build_changes.main(["--csv", str(csv_file), "--out", str(out)]) == 0
    assert "# Listing changes" in out.read_text(encoding="utf-8")


def test_a_missing_csv_is_a_one_not_a_two(tmp_path):
    code = build_changes.main(["--csv", str(tmp_path / "nope.csv")])
    assert code == 1


def test_history_trouble_still_writes_the_file(tmp_path, csv_file, monkeypatch):
    """The changelog must never cost a day's data."""
    out = tmp_path / "out.md"
    monkeypatch.setattr(build_changes, "_history",
                        lambda **kw: ([], "shallow clone"))
    # A 1, not a 0: update.py's own docstring promises it, and a silent 0
    # means CI goes green while the published file says history was missing.
    assert build_changes.main(["--csv", str(csv_file), "--out", str(out)]) == 1
    assert "shallow clone" in out.read_text(encoding="utf-8")


def test_a_non_integer_day_count_is_a_misconfiguration(csv_file):
    """Review Focus 5."""
    assert build_changes.main(["--csv", str(csv_file), "--days", "banana"]) == 2


def test_a_day_count_below_one_is_a_misconfiguration(csv_file):
    """Review Focus 5."""
    assert build_changes.main(["--csv", str(csv_file), "--days", "0"]) == 2


def test_the_file_ends_with_one_newline(tmp_path, csv_file, monkeypatch):
    out = tmp_path / "out.md"
    monkeypatch.setattr(build_changes, "_history", lambda **kw: ([], ""))
    build_changes.main(["--csv", str(csv_file), "--out", str(out)])
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_one_unreadable_revision_is_skipped_not_fatal(tmp_path, csv_file,
                                                     monkeypatch):
    """The CSV may not exist that far back; the rest of the window still counts."""
    from bendrentals.history import GitUnavailable

    monkeypatch.setattr(build_changes, "daily_revisions",
                        lambda **kw: [("2026-01-10", "aaaa1111"),
                                      ("2026-01-09", "bbbb2222")])

    def rows_at(sha, **kw):
        if sha == "bbbb2222":
            raise GitUnavailable("path did not exist at that revision")
        return {}
    monkeypatch.setattr(build_changes, "rows_at", rows_at)

    out = tmp_path / "out.md"
    assert build_changes.main(["--csv", str(csv_file), "--out", str(out)]) == 0
    assert "# Listing changes" in out.read_text(encoding="utf-8")


def test_geocode_cache_exposes_its_entries(tmp_path):
    path = tmp_path / "geocode.json"
    cache = GeocodeCache(path)
    cache.put("1 Main St, Bend, OR", "44.0", "-121.0")
    assert any(e["lat"] == "44.0" for e in cache.entries.values())


def test_todays_movement_is_reported_not_just_yesterdays(tmp_path, monkeypatch):
    """CI builds this before committing, so today exists only in the working tree.

    Without today appended as a history entry, the newest dated section is
    yesterday while the header asserts today's run date, and the one thing a
    reader opens the file for is a day late.
    """
    csv_path = tmp_path / "listings.csv"
    write_csv(csv_path, [
        {"company": "A", "link": "https://x/1", "address": "Kept Rd",
         "price": "1000", "scraped_at": "2026-01-11T08:00:00", "lat": "44.0"},
        {"company": "A", "link": "https://x/2", "address": "Brand New Rd",
         "price": "1200", "scraped_at": "2026-01-11T08:00:00", "lat": "44.0"},
    ])
    # The committed history ends yesterday and has never seen https://x/2.
    monkeypatch.setattr(build_changes, "daily_revisions",
                        lambda **kw: [("2026-01-10", "bbbb2222"),
                                      ("2026-01-09", "aaaa1111")])
    monkeypatch.setattr(build_changes, "rows_at", lambda sha, **kw: {
        "https://x/1": {"company": "A", "link": "https://x/1",
                        "address": "Kept Rd", "price": "1000"},
    })
    out = tmp_path / "out.md"
    assert build_changes.main(["--csv", str(csv_path), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "### 2026-01-11" in text
    assert "Brand New Rd" in text


def test_a_rebuild_after_the_commit_does_not_duplicate_today(tmp_path, monkeypatch):
    """Run locally after the day's commit, today is already in git."""
    csv_path = tmp_path / "listings.csv"
    write_csv(csv_path, [
        {"company": "A", "link": "https://x/1", "address": "Kept Rd",
         "price": "1000", "scraped_at": "2026-01-11T08:00:00", "lat": "44.0"},
    ])
    monkeypatch.setattr(build_changes, "daily_revisions",
                        lambda **kw: [("2026-01-11", "bbbb2222"),
                                      ("2026-01-10", "aaaa1111")])
    monkeypatch.setattr(build_changes, "rows_at", lambda sha, **kw: {
        "https://x/1": {"company": "A", "link": "https://x/1",
                        "address": "Kept Rd", "price": "1000"},
    })
    out = tmp_path / "out.md"
    assert build_changes.main(["--csv", str(csv_path), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.count("### 2026-01-11") == 1


def _window_sections(tmp_path, monkeypatch, revisions, today_stamp):
    """Build with a given committed history and return the dated section count."""
    csv_path = tmp_path / "listings.csv"
    write_csv(csv_path, [{"company": "A", "link": "https://x/1",
                          "address": "Kept Rd", "price": "1000",
                          "scraped_at": f"{today_stamp}T08:00:00", "lat": "44.0"}])
    monkeypatch.setattr(build_changes, "daily_revisions",
                        lambda **kw: revisions[:kw["days"]])
    monkeypatch.setattr(build_changes, "rows_at", lambda sha, **kw: {
        "https://x/1": {"company": "A", "link": "https://x/1",
                        "address": "Kept Rd", "price": "1000"},
    })
    out = tmp_path / "out.md"
    assert build_changes.main(
        ["--csv", str(csv_path), "--out", str(out), "--days", "3"]) == 0
    return out.read_text(encoding="utf-8").count("\n### ")


# Ten days of committed history, newest first, as daily_revisions returns them.
TEN_DAYS = [(f"2026-01-{20 - n:02d}", f"sha{n}") for n in range(10)]


def test_the_window_is_the_requested_number_of_days_when_today_is_uncommitted(
        tmp_path, monkeypatch):
    """The CI case: the newest commit is yesterday, today is in the tree."""
    assert _window_sections(tmp_path, monkeypatch, TEN_DAYS, "2026-01-21") == 3


def test_the_window_is_the_same_when_today_is_already_committed(
        tmp_path, monkeypatch):
    """The local-rebuild case. The window must not shrink by one."""
    assert _window_sections(tmp_path, monkeypatch, TEN_DAYS, "2026-01-20") == 3
