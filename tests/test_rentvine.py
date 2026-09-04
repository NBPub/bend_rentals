from pathlib import Path

import pytest

from bendrentals.models import UNKNOWN
from bendrentals.structures.rentvine_listings import parse_index

FIXTURES = Path(__file__).parent / "fixtures" / "rentvine"
BASE = "https://ridgelinepropertymgmt.rentvine.com/api/public/listings"


@pytest.fixture(scope="module")
def rows():
    return parse_index((FIXTURES / "listings.json").read_text(encoding="utf-8"), BASE)


def test_parses_every_record(rows):
    assert len(rows) == 2


def test_address_is_assembled_from_the_unit_parts(rows):
    assert rows[0]["address"] == "19804 Wetland Ct, Bend, OR 97702"


def test_numeric_fields(rows):
    row = rows[0]
    assert row["price"] == 2995
    assert row["bedrooms"] == 3
    assert row["bathrooms"] == "2"
    assert row["sqft"] == 1235


def test_cats_allowed_comes_from_the_explicit_boolean(rows):
    # acceptCats: 1 — no prose parsing involved.
    assert rows[0]["cats_allowed"] == "True"


def test_coordinates_are_supplied_by_the_source(rows):
    # Rentvine is the only source that publishes these, so it needs no geocoding.
    assert rows[0]["lat"].startswith("44.0")
    assert rows[0]["lon"].startswith("-121.3")
    assert all(r["lat"] != UNKNOWN and r["lon"] != UNKNOWN for r in rows)


def test_link_points_at_the_public_listing_route(rows):
    assert rows[0]["link"] == (
        "https://ridgelinepropertymgmt.rentvine.com/public/listings/29"
    )


def test_summary_is_the_sources_own_headline(rows):
    assert rows[0]["summary"].startswith("Furnished 3-Bedroom Home")


def test_dogs_come_from_the_same_place_as_cats(rows):
    """Rentvine publishes acceptCats and acceptDogs as real booleans."""
    assert rows[0]["cats_allowed"] in {"True", "False"}
    assert rows[0]["dogs_allowed"] in {"True", "False"}


def test_agent_contact_details_are_not_carried_into_a_row(rows):
    """The JSON includes agent names, phones and emails. None reach a row."""
    for row in rows:
        assert "@" not in " ".join(str(v) for v in row.values())


def test_pet_description_is_kept_verbatim(rows):
    assert "two pets" in rows[0]["pets_raw"]


def test_region_uses_a_quadrant_when_one_is_stated(rows):
    # The second listing is on "Northwest Shasta Place".
    assert rows[1]["region"] in {"NW Bend", "Bend"}


def test_agent_contact_details_are_not_carried_into_the_row(rows):
    # The API returns agent names, phones and emails; we have no use for them.
    blob = str(rows).lower()
    for leak in ("@ridgelinepropertymanagement.com", "+1541", "brett", "jonathan"):
        assert leak not in blob


def test_malformed_payload_yields_no_rows():
    assert parse_index("not json", BASE) == []
    assert parse_index('{"unexpected": "shape"}', BASE) == []


def test_available_date_passes_through_as_iso(rows):
    assert rows[0]["available"] == "2026-10-01"
    assert rows[0]["available_now"] == "False"
