import re
from pathlib import Path

import pytest

from bendrentals.models import UNKNOWN
from bendrentals.structures.appfolio_listings import parse_index

FIXTURES = Path(__file__).parent / "fixtures" / "appfolio"
BASE = "https://mountainviewpm.appfolio.com/listings"


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rows():
    return parse_index(read("index_all.html"), BASE)


def test_parses_every_card(rows):
    assert len(rows) == 16


def test_links_are_absolute_and_unique(rows):
    assert all(r["link"].startswith("https://mountainviewpm.appfolio.com/listings/detail/")
               for r in rows)
    assert len({r["link"] for r in rows}) == 16


def test_core_fields_of_a_known_listing(rows):
    row = next(r for r in rows if "Schaeffer" in r["address"])
    assert row["price"] == 2395
    assert row["bedrooms"] == 3
    assert row["bathrooms"] == "2.5"
    assert row["sqft"] == 1485
    assert row["address"] == "20287 Schaeffer Dr., Bend, OR 97703"
    assert row["summary"].startswith("Beautiful 3 Bed/2.5 Bath Two-Story Duplex")
    assert "description" not in row      # read while parsing, never stored



def test_region_derives_quadrant_from_the_listing(rows):
    row = next(r for r in rows if "Schaeffer" in r["address"])
    assert row["region"] == "NW Bend"


def test_every_row_has_a_price_and_bedroom_count(rows):
    assert all(isinstance(r["price"], int) for r in rows)
    assert all(r["bedrooms"] != UNKNOWN for r in rows)


def test_pets_raw_strips_the_label(rows):
    values = {r["pets_raw"] for r in rows}
    assert "Cats allowed, Dogs allowed" in values
    assert not any(v.startswith("Pet Policy:") for v in values)


def test_cats_allowed_three_way_split(rows):
    counts = {}
    for r in rows:
        counts[r["cats_allowed"]] = counts.get(r["cats_allowed"], 0) + 1
    # 12 allow cats, 2 explicitly do not, 2 say nothing about cats.
    assert counts == {"True": 12, "False": 2, UNKNOWN: 2}


def test_cats_allowed_matches_appfolios_own_filter():
    """Cross-check: parsing the card must agree with AppFolio's cats filter.

    The filtered pages were captured in the same session as index_all.html.
    If these ever disagree, the card-text parser is wrong.
    """
    everything = parse_index(read("index_all.html"), BASE)
    yes = {r["link"] for r in parse_index(read("index_cats_yes.html"), BASE)}
    no = {r["link"] for r in parse_index(read("index_cats_no.html"), BASE)}

    assert not (yes & no), "a listing cannot both allow and forbid cats"
    for row in everything:
        if row["link"] in yes:
            assert row["cats_allowed"] == "True"
        elif row["link"] in no:
            assert row["cats_allowed"] == "False"
        else:
            assert row["cats_allowed"] == UNKNOWN


def test_a_listing_with_no_pet_policy_is_unknown_not_false(rows):
    # "no policy stated" must never be read as "cats forbidden".
    silent = [r for r in rows if r["cats_allowed"] == UNKNOWN]
    assert silent
    assert all("Cats" not in r["pets_raw"] for r in silent)


def test_empty_page_yields_no_rows():
    assert parse_index("<html><body>nothing here</body></html>", BASE) == []


def test_available_dates_are_iso(rows):
    dated = [r for r in rows if r["available"] != UNKNOWN]
    assert dated
    for row in dated:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["available"]), row["available"]
        assert row["available_now"] == "False"


def test_immediate_availability_sets_the_flag_not_a_date(rows):
    # Four of these sixteen cards say "NOW" rather than a date.
    now = [r for r in rows if r["available_now"] == "True"]
    assert len(now) == 4
    assert all(r["available"] == UNKNOWN for r in now)
