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
    monkeypatch.setattr(build_changes, "_history",
                        lambda **kw: ([], "no repo here"))
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
    assert build_changes.main(["--csv", str(csv_file), "--out", str(out)]) == 0
    assert "shallow clone" in out.read_text(encoding="utf-8")


def test_a_non_integer_day_count_is_a_misconfiguration(csv_file):
    """Review Focus 5."""
    assert build_changes.main(["--csv", str(csv_file), "--days", "banana"]) == 2


def test_a_day_count_below_one_is_a_misconfiguration(csv_file):
    """Review Focus 5."""
    assert build_changes.main(["--csv", str(csv_file), "--days", "0"]) == 2


def test_the_file_ends_with_one_newline(tmp_path, csv_file, monkeypatch):
    out = tmp_path / "out.md"
    monkeypatch.setattr(build_changes, "_history", lambda **kw: ([], "none"))
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
