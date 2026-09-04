import csv

import pytest

from bendrentals.models import Listing
from build_page import DEFAULT_OUT, flag_value, main


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=Listing.fieldnames())
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def row(**overrides):
    base = dict.fromkeys(Listing.fieldnames(), "?")
    base.update(
        company="Trailhead Property Management", link="https://example.com/1",
        address="1 A St, Bend, OR 97701", region="SW Bend", price="2495",
        bedrooms="3", bathrooms="2.5", sqft="1500", cats_allowed="True",
        dogs_allowed="False", maps_link="https://maps.example.com/1",
        summary="A house", lat="44.05", lon="-121.31", parse_status="ok",
    )
    base.update(overrides)
    return base


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_csv(tmp_path / "data" / "listings.csv", [row()])
    return tmp_path


def test_writes_the_page_where_pages_serves_from(project, capsys):
    assert main([]) == 0
    out = project / DEFAULT_OUT
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert "1 mapped" in capsys.readouterr().out


def test_the_output_directory_is_created_if_missing(project):
    assert not (project / "docs").exists()
    main([])
    assert (project / "docs" / "index.html").exists()


def test_out_can_be_redirected(project):
    assert main(["--out", "elsewhere.html"]) == 0
    assert (project / "elsewhere.html").exists()


def test_a_different_csv_can_be_read(project):
    write_csv(project / "other.csv", [row(address="9 B St, Bend, OR 97701")])
    assert main(["--csv", "other.csv", "--out", "o.html"]) == 0
    assert "9 B St" in (project / "o.html").read_text(encoding="utf-8")


def test_a_missing_csv_says_to_scrape_first(project, capsys):
    (project / "data" / "listings.csv").unlink()
    assert main([]) == 1
    assert "scrape.py" in capsys.readouterr().err


def test_a_csv_with_only_a_header_is_an_error_not_an_empty_page(project, capsys):
    write_csv(project / "data" / "listings.csv", [])
    assert main([]) == 1
    assert "no listings" in capsys.readouterr().err


def test_a_csv_predating_a_schema_change_names_the_column(project, capsys):
    path = project / "data" / "listings.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write("company,address\nA Co,1 A St\n")
    assert main([]) == 1
    err = capsys.readouterr().err
    assert "lat" in err and "scrape.py" in err


def test_an_unknown_tile_provider_exits_two_and_lists_the_real_ones(project, capsys):
    assert main(["--tiles", "nonsense"]) == 2
    assert "esri" in capsys.readouterr().err


def test_listings_without_coordinates_are_named_on_stdout(project, capsys):
    write_csv(project / "data" / "listings.csv",
              [row(), row(address="?", lat="?", lon="?")])
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "1 without coordinates" in out
    assert "no address published" in out


def test_flag_value_falls_back_when_absent():
    assert flag_value([], "--tiles", "esri") == "esri"


def test_flag_value_at_the_end_of_argv_does_not_crash():
    assert flag_value(["--tiles"], "--tiles", "esri") == "esri"
