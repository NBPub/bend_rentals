import json

import pytest

from bendrentals.mapdata import (
    FACET_FIELDS,
    PRICE_BANDS,
    RANGE_FIELDS,
    UNKNOWN_BAND,
    UNSTATED,
    city_of_region,
    embed_json,
    facet_value,
    facets,
    number,
    price_band,
    ranges,
    records_from_rows,
    safe_link,
)
from bendrentals.models import Listing


def row(**overrides):
    base = dict.fromkeys(Listing.fieldnames(), "?")
    base.update(
        company="Trailhead Property Management",
        link="https://example.com/1",
        address="1 A St, Bend, OR 97701",
        region="SW Bend", price="2495", bedrooms="3", bathrooms="2.5",
        sqft="1500", available="2026-10-01", available_now="False",
        cats_allowed="True", dogs_allowed="False",
        maps_link="https://maps.example.com/1",
        summary="A house", lat="44.05", lon="-121.31",
        scraped_at="2026-09-01T09:00:00", parse_status="ok",
    )
    base.update(overrides)
    return base


# --- numbers and bands ------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("2495", 2495.0), ("$1,495.00", 1495.0), ("-121.334", -121.334),
    (2495, 2495.0), ("", None), ("?", None), (None, None), ("n/a", None),
])
def test_number_reads_what_a_cell_may_hold(text, expected):
    assert number(text) == expected


@pytest.mark.parametrize("price,label", [
    (0, "under $1,000"),
    (999, "under $1,000"),
    (1000, "$1,000 - $1,499"),
    (1499, "$1,000 - $1,499"),
    (1500, "$1,500 - $1,999"),
    (1999, "$1,500 - $1,999"),
    (2000, "$2,000 - $2,499"),
    (2499, "$2,000 - $2,499"),
    (2500, "$2,500 - $2,999"),
    (2999, "$2,500 - $2,999"),
    (3000, "$3,000 and up"),
    (9500, "$3,000 and up"),
])
def test_price_bands_have_no_gap_at_a_boundary(price, label):
    assert price_band(price)["label"] == label


def test_the_bands_are_five_hundred_wide_between_one_and_three_thousand():
    assert [b["below"] for b in PRICE_BANDS] == [1000, 1500, 2000, 2500, 3000, None]


def test_every_band_label_agrees_with_its_own_boundary():
    """A label that disagrees with its threshold misleads silently.

    Derived rather than hard-coded, so it keeps checking after the next
    change to the bands.
    """
    first, *middle, last = PRICE_BANDS

    # The ends are worded as open ranges, so each names one number, not two.
    assert f"{first['below']:,}" in first["label"], first

    floor = first["below"]
    for band in middle:
        assert f"{floor:,}" in band["label"], band
        assert f"{band['below'] - 1:,}" in band["label"], band
        floor = band["below"]

    assert f"{floor:,}" in last["label"], last


def test_the_bands_are_contiguous_and_ordered():
    ceilings = [b["below"] for b in PRICE_BANDS]
    assert ceilings[-1] is None, "the last band must have no ceiling"
    assert ceilings[:-1] == sorted(ceilings[:-1])
    assert len(set(ceilings[:-1])) == len(ceilings) - 1


def test_bands_are_distinct_colours():
    colours = [b["colour"] for b in PRICE_BANDS] + [UNKNOWN_BAND["colour"]]
    assert len(set(colours)) == len(colours)


def test_an_unreadable_price_still_gets_a_marker():
    assert price_band("?") is UNKNOWN_BAND
    assert price_band("") is UNKNOWN_BAND


# --- links ------------------------------------------------------------------

@pytest.mark.parametrize("value", [
    "javascript:alert(1)", "data:text/html,<script>", "vbscript:x", "?", "",
])
def test_only_http_urls_survive(value):
    assert safe_link(value) == ""


def test_http_and_https_are_kept():
    assert safe_link("https://x.example/1") == "https://x.example/1"
    assert safe_link("http://x.example/1") == "http://x.example/1"


# --- records ----------------------------------------------------------------

def test_a_row_becomes_a_record_with_numbers_parsed():
    mapped, unmapped = records_from_rows([row()])
    assert not unmapped
    record = mapped[0]
    assert record["price"] == 2495.0
    assert record["bedrooms"] == 3.0
    assert record["sqft"] == 1500.0
    assert record["bathrooms"] == "2.5"          # a string, so it can hold "?"
    assert record["lat"] == 44.05 and record["lon"] == -121.31
    assert record["band"]["label"] == "$2,000 - $2,499"


def test_unknown_becomes_blank_rather_than_a_question_mark():
    """On a page, "the site did not say" should read as silence."""
    record = records_from_rows([row(available="?", summary="?")])[0][0]
    assert record["available"] == ""
    assert record["summary"] == ""


def test_a_listing_without_coordinates_is_kept_separately_not_dropped():
    mapped, unmapped = records_from_rows([row(lat="?", lon="?")])
    assert not mapped
    assert len(unmapped) == 1
    assert unmapped[0]["address"] == "1 A St, Bend, OR 97701"


def test_a_missing_column_names_itself():
    broken = row()
    del broken["lat"]
    with pytest.raises(ValueError, match="lat"):
        records_from_rows([broken])


def test_blank_rows_are_skipped():
    assert records_from_rows([{k: "" for k in row()}]) == ([], [])


def test_dangerous_links_do_not_reach_a_record():
    record = records_from_rows([row(link="javascript:alert(1)")])[0][0]
    assert record["link"] == ""


def test_the_long_description_is_not_carried_onto_the_page():
    record = records_from_rows([row()])[0][0]
    assert "description" not in record


# --- facets and ranges ------------------------------------------------------

def test_every_facet_field_gets_options():
    records = records_from_rows([row(), row(region="NE Bend", bedrooms="2")])[0]
    found = facets(records)
    assert set(found) == set(FACET_FIELDS)
    assert [o["value"] for o in found["region"]] == ["NE Bend", "SW Bend"]


def test_numeric_facets_sort_as_numbers_not_as_text():
    records = records_from_rows(
        [row(bedrooms=n) for n in ("2", "10", "1")])[0]
    assert [o["value"] for o in facets(records)["bedrooms"]] == ["1", "2", "10"]


def test_a_studio_is_zero_bedrooms_not_an_unstated_one():
    """`or ""` here would file every studio under "not stated"."""
    records = records_from_rows([row(bedrooms="0"), row(bedrooms="2")])[0]
    options = facets(records)["bedrooms"]
    assert [o["value"] for o in options] == ["0", "2"]
    assert [o["label"] for o in options] == ["0", "2"]


@pytest.mark.parametrize("value,expected", [
    (3.0, "3"),          # JS String(3.0) is "3"; Python's str() is "3.0"
    (2.5, "2.5"),
    (0.0, "0"),
    ("2.5", "2.5"),
    ("", ""),
    (None, ""),
])
def test_facet_value_writes_the_spelling_a_browser_will_produce(value, expected):
    assert facet_value(value) == expected


def test_an_unstated_value_is_offered_and_labelled():
    records = records_from_rows([row(), row(cats_allowed="?")])[0]
    options = facets(records)["cats_allowed"]
    assert {"value": "", "label": UNSTATED, "city": ""} in options


def test_unstated_options_sort_last():
    records = records_from_rows([row(bathrooms="?"), row(bathrooms="1")])[0]
    assert [o["label"] for o in facets(records)["bathrooms"]] == ["1", UNSTATED]


def test_region_options_carry_their_city():
    """The page needs it to know "Bend" could be any Bend quadrant."""
    records = records_from_rows([row(region="NW Bend"), row(region="Bend"),
                                 row(region="Redmond")])[0]
    cities = {o["value"]: o["city"] for o in facets(records)["region"]}
    assert cities == {"NW Bend": "Bend", "Bend": "Bend", "Redmond": "Redmond"}


@pytest.mark.parametrize("region,city", [
    ("NW Bend", "Bend"), ("SE Bend", "Bend"), ("Bend", "Bend"),
    ("Redmond", "Redmond"), ("", ""), ("?", "?"),
])
def test_city_of_region(region, city):
    assert city_of_region(region) == city


def test_ranges_report_what_is_actually_present():
    records = records_from_rows(
        [row(price="900", sqft="700"), row(price="4200", sqft="3000")])[0]
    found = ranges(records)
    assert set(found) == set(RANGE_FIELDS)
    assert found["price"] == {"min": 900.0, "max": 4200.0}


def test_a_range_with_no_readable_value_is_null_not_zero():
    """Zero would look like a real bound and silently filter everything out."""
    records = records_from_rows([row(sqft="?")])[0]
    assert ranges(records)["sqft"] == {"min": None, "max": None}


# --- embedding --------------------------------------------------------------

def test_embed_json_escapes_a_closing_script_tag():
    """json.dumps emits </script> verbatim, which ends the block regardless."""
    embedded = embed_json({"summary": "</script><img src=x onerror=alert(1)>"})
    assert "</script>" not in embedded
    assert "<" not in embedded


def test_embed_json_escapes_the_line_separators_that_end_a_js_string():
    for char in (" ", " "):
        assert char not in embed_json({"x": char})


def test_embed_json_still_round_trips():
    payload = {"summary": "</script>", "sep": " ", "price": 2495}
    assert json.loads(embed_json(payload)) == payload
