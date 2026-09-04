import csv

import pytest

from bendrentals.diff import (
    IGNORED_FIELDS,
    diff_snapshots,
    format_report,
    latest_snapshots,
    read_snapshot,
)
from bendrentals.models import Listing


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=Listing.fieldnames())
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def row(link, price="3550", address="19884 Duck Call Lane, Bend OR 97702", scraped_at="A"):
    base = dict.fromkeys(Listing.fieldnames(), "")
    base.update(link=link, price=price, address=address, scraped_at=scraped_at,
                bedrooms="3", bathrooms="2.5", region="SW Bend", parse_status="ok")
    return base


def test_reads_snapshot_keyed_by_link(tmp_path):
    path = tmp_path / "a.csv"
    write_csv(path, [row("https://x/1"), row("https://x/2")])
    snapshot = read_snapshot(path)
    assert sorted(snapshot) == ["https://x/1", "https://x/2"]
    assert snapshot["https://x/1"]["price"] == "3550"


def test_detects_added_listing(tmp_path):
    write_csv(tmp_path / "old.csv", [row("https://x/1")])
    write_csv(tmp_path / "new.csv", [row("https://x/1"), row("https://x/2")])
    result = diff_snapshots(read_snapshot(tmp_path / "old.csv"),
                            read_snapshot(tmp_path / "new.csv"))
    assert list(result["added"]) == ["https://x/2"]
    assert result["removed"] == {}
    assert result["changed"] == {}


def test_detects_removed_listing(tmp_path):
    write_csv(tmp_path / "old.csv", [row("https://x/1"), row("https://x/2")])
    write_csv(tmp_path / "new.csv", [row("https://x/1")])
    result = diff_snapshots(read_snapshot(tmp_path / "old.csv"),
                            read_snapshot(tmp_path / "new.csv"))
    assert list(result["removed"]) == ["https://x/2"]


def test_detects_price_change(tmp_path):
    write_csv(tmp_path / "old.csv", [row("https://x/1", price="3550")])
    write_csv(tmp_path / "new.csv", [row("https://x/1", price="3400")])
    result = diff_snapshots(read_snapshot(tmp_path / "old.csv"),
                            read_snapshot(tmp_path / "new.csv"))
    assert result["changed"]["https://x/1"]["price"] == ("3550", "3400")


def test_scraped_at_change_alone_is_not_a_change(tmp_path):
    assert "scraped_at" in IGNORED_FIELDS
    write_csv(tmp_path / "old.csv", [row("https://x/1", scraped_at="A")])
    write_csv(tmp_path / "new.csv", [row("https://x/1", scraped_at="B")])
    result = diff_snapshots(read_snapshot(tmp_path / "old.csv"),
                            read_snapshot(tmp_path / "new.csv"))
    assert result["changed"] == {}


def test_report_is_readable(tmp_path):
    write_csv(tmp_path / "old.csv", [row("https://x/1", price="3550"), row("https://x/2")])
    write_csv(tmp_path / "new.csv", [row("https://x/1", price="3400"), row("https://x/3")])
    result = diff_snapshots(read_snapshot(tmp_path / "old.csv"),
                            read_snapshot(tmp_path / "new.csv"))
    report = format_report(result, "old.csv", "new.csv")
    assert "old.csv" in report and "new.csv" in report
    assert "price" in report and "3550" in report and "3400" in report
    assert "https://x/3" in report
    assert "https://x/2" in report


def test_report_says_no_changes_when_identical(tmp_path):
    write_csv(tmp_path / "old.csv", [row("https://x/1")])
    write_csv(tmp_path / "new.csv", [row("https://x/1")])
    result = diff_snapshots(read_snapshot(tmp_path / "old.csv"),
                            read_snapshot(tmp_path / "new.csv"))
    assert "No changes" in format_report(result, "old.csv", "new.csv")


def test_latest_snapshots_picks_the_two_most_recent(tmp_path):
    snaps = tmp_path / "data" / "snapshots"
    for name in ("2026-08-30T090000.csv", "2026-08-31T142207.csv", "2026-09-01T090500.csv"):
        write_csv(snaps / name, [row("https://x/1")])
    older, newer = latest_snapshots(root=tmp_path)
    assert older.name == "2026-08-31T142207.csv"
    assert newer.name == "2026-09-01T090500.csv"


def test_latest_snapshots_needs_at_least_two(tmp_path):
    snaps = tmp_path / "data" / "snapshots"
    write_csv(snaps / "2026-08-31T142207.csv", [row("https://x/1")])
    with pytest.raises(ValueError, match="at least two"):
        latest_snapshots(root=tmp_path)


def test_coordinates_moving_is_not_reported_as_a_change(tmp_path):
    """Geocoding improving is not a listing changing.

    When the Census fallback was added it resolved 21 previously-unknown
    addresses; without this, every one would have been reported as "changed".
    """
    assert {"lat", "lon"} <= IGNORED_FIELDS

    before = row("https://x/1")
    before.update(lat="?", lon="?")
    after = row("https://x/1")
    after.update(lat="44.05130", lon="-121.27597")
    write_csv(tmp_path / "old.csv", [before])
    write_csv(tmp_path / "new.csv", [after])

    result = diff_snapshots(read_snapshot(tmp_path / "old.csv"),
                            read_snapshot(tmp_path / "new.csv"))
    assert result["changed"] == {}


def test_a_real_change_alongside_new_coordinates_is_still_reported(tmp_path):
    before = row("https://x/1", price="3550")
    before.update(lat="?", lon="?")
    after = row("https://x/1", price="3400")
    after.update(lat="44.05", lon="-121.27")
    write_csv(tmp_path / "old.csv", [before])
    write_csv(tmp_path / "new.csv", [after])

    result = diff_snapshots(read_snapshot(tmp_path / "old.csv"),
                            read_snapshot(tmp_path / "new.csv"))
    assert result["changed"]["https://x/1"] == {"price": ("3550", "3400")}
