import csv
from datetime import datetime

from bendrentals.csv_out import (
    SNAPSHOT_FORMAT, merge_rows, read_rows, write_rows,
)
from bendrentals.models import UNKNOWN, Listing

WHEN = datetime(2026, 8, 31, 14, 22, 7)
TRAILHEAD = "Trailhead Property Management"
RIDGELINE = "Ridgeline Property Management"


def make_row(link="https://example.com/a", price=3550, company=TRAILHEAD):
    return Listing(
        company=company, link=link, price=price, bedrooms=3, bathrooms="2.5",
        sqft=2472, property_type=UNKNOWN, region="SW Bend",
        available="2026-09-15", available_now="False",
        address="19884 Duck Call Lane, Bend OR 97702",
        cats_allowed="True", dogs_allowed=UNKNOWN,
        maps_link="https://maps", lat="44.0", lon="-121.3",
        summary="Amazing home", pets_raw=UNKNOWN,
        scraped_at="2026-08-31T14:22:07", parse_status="ok",
    ).to_row()


def test_writes_one_csv_for_every_source(tmp_path):
    csv_path, snap_path = write_rows([make_row()], when=WHEN, root=tmp_path)
    assert csv_path == tmp_path / "data" / "listings.csv"
    assert snap_path == tmp_path / "data" / "snapshots" / "2026-08-31T142207.csv"
    assert csv_path.exists() and snap_path.exists()


def test_snapshot_filename_has_no_colons():
    # Colons are invalid in Windows filenames.
    assert ":" not in datetime.now().strftime(SNAPSHOT_FORMAT)


def test_header_matches_the_model_field_order(tmp_path):
    csv_path, _ = write_rows([make_row()], when=WHEN, root=tmp_path)
    with open(csv_path, newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == Listing.fieldnames()


def test_snapshot_is_byte_identical_to_the_current_csv(tmp_path):
    csv_path, snap_path = write_rows([make_row()], when=WHEN, root=tmp_path)
    assert csv_path.read_bytes() == snap_path.read_bytes()


def test_the_snapshot_can_be_skipped(tmp_path):
    """CI keeps its history in git, so a dated copy per run is just noise."""
    csv_path, snap_path = write_rows(
        [make_row()], when=WHEN, root=tmp_path, snapshot=False)
    assert snap_path is None
    assert csv_path.exists()
    assert not (tmp_path / "data" / "snapshots").exists()


def test_rerun_overwrites_the_csv_but_keeps_both_snapshots(tmp_path):
    write_rows([make_row(price=3550)], when=WHEN, root=tmp_path)
    later = datetime(2026, 9, 1, 9, 5, 0)
    csv_path, _ = write_rows([make_row(price=3400)], when=later, root=tmp_path)

    rows = read_rows(csv_path)
    assert len(rows) == 1
    assert rows[0]["price"] == "3400"
    assert len(sorted((tmp_path / "data" / "snapshots").iterdir())) == 2


def test_unknown_values_are_written_as_question_marks(tmp_path):
    row = make_row()
    row["bathrooms"] = UNKNOWN
    csv_path, _ = write_rows([row], when=WHEN, root=tmp_path)
    assert read_rows(csv_path)[0]["bathrooms"] == "?"


def test_quoted_text_survives_a_csv_round_trip(tmp_path):
    row = make_row()
    row["summary"] = 'He said "great", then left.'
    csv_path, _ = write_rows([row], when=WHEN, root=tmp_path)
    assert read_rows(csv_path)[0]["summary"] == 'He said "great", then left.'


def test_read_rows_of_a_missing_file_is_empty(tmp_path):
    assert read_rows(tmp_path / "nothing.csv") == []


# --- merging: the guarantee the per-site CSVs used to give for free ---------

def test_a_partial_run_keeps_the_companies_it_did_not_scrape():
    existing = [make_row(company=TRAILHEAD), make_row(company=RIDGELINE)]
    fresh = [make_row(link="https://example.com/new", company=TRAILHEAD)]

    merged = merge_rows(fresh, {TRAILHEAD}, existing)

    assert [r["company"] for r in merged] == [TRAILHEAD, RIDGELINE]
    assert merged[0]["link"] == "https://example.com/new"


def test_a_refreshed_company_replaces_all_of_its_old_rows():
    existing = [make_row(link="https://example.com/a"),
                make_row(link="https://example.com/b")]
    merged = merge_rows([make_row(link="https://example.com/c")],
                        {TRAILHEAD}, existing)
    assert [r["link"] for r in merged] == ["https://example.com/c"]


def test_a_site_that_failed_keeps_its_previous_listings():
    """A site being down must not delete that company from the file."""
    existing = [make_row(company=TRAILHEAD), make_row(company=RIDGELINE)]
    # Ridgeline raised, so it is absent from `refreshed`.
    merged = merge_rows([make_row(company=TRAILHEAD)], {TRAILHEAD}, existing)
    assert RIDGELINE in {r["company"] for r in merged}


def test_a_full_run_with_no_existing_file_just_writes_the_fresh_rows():
    fresh = [make_row(company=TRAILHEAD), make_row(company=RIDGELINE)]
    assert merge_rows(fresh, {TRAILHEAD, RIDGELINE}, []) == fresh
