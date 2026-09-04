import json
import re
from datetime import datetime

import pytest

from bendrentals.mapdata import records_from_rows
from bendrentals.models import Listing
from bendrentals.pagehtml import (
    DEFAULT_CSV_URL,
    DEFAULT_TILES,
    FIELD_LABELS,
    POPUP_FIELDS,
    REPO_URL,
    TABLE_FIELDS,
    TILE_PROVIDERS,
    render,
)

WHEN = datetime(2026, 9, 3, 10, 30)


def row(**overrides):
    base = dict.fromkeys(Listing.fieldnames(), "?")
    base.update(
        company="Trailhead Property Management", link="https://example.com/1",
        address="1 A St, Bend, OR 97701", region="SW Bend", price="2495",
        bedrooms="3", bathrooms="2.5", sqft="1500", available="2026-10-01",
        available_now="False", cats_allowed="True", dogs_allowed="False",
        maps_link="https://maps.example.com/1", summary="A house",
        lat="44.05", lon="-121.31", scraped_at="2026-09-01T09:00:00",
        parse_status="ok",
    )
    base.update(overrides)
    return base


def build(rows=None, **kwargs):
    mapped, unmapped = records_from_rows(rows or [row()])
    return render(mapped, unmapped, generated_at=WHEN, **kwargs)


def payload_of(html):
    match = re.search(
        r'<script id="payload" type="application/json">(.*?)</script>',
        html, re.S)
    assert match, "no payload block in the page"
    return json.loads(match.group(1))


# --- the document ------------------------------------------------------------

def test_renders_a_complete_document():
    html = build()
    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")


def test_every_placeholder_is_substituted():
    """A leftover __TOKEN__ would ship as visible text or a broken script."""
    assert not re.search(r"__[A-Z_]+__", build())


def test_the_page_needs_only_leaflet_from_the_network():
    html = build()
    sources = re.findall(r'<script src="([^"]+)"', html)
    assert all("leaflet" in src for src in sources)


def test_the_page_carries_the_elements_its_script_looks_for():
    html = build()
    for element_id in ("payload", "map", "filters", "unmapped", "legend",
                       "count", "head", "body", "csvlink", "fit"):
        assert f'id="{element_id}"' in html, element_id


# --- data reaches the page only as escaped JSON ------------------------------

def test_a_closing_script_tag_in_a_summary_cannot_break_out():
    html = build([row(summary="</script><img src=x onerror=alert(1)>")])
    assert "<img src=x" not in html
    assert html.count("</script>") == html.count("<script")


def test_listing_text_is_never_interpolated_into_markup():
    marker = "UNIQUE-SUMMARY-MARKER"
    html = build([row(summary=marker)])
    # It appears once, inside the JSON block, and nowhere else.
    assert html.count(marker) == 1
    assert marker in payload_of(html)["records"][0]["summary"]


def test_a_javascript_url_never_reaches_the_page():
    html = build([row(link="javascript:alert(1)")])
    assert "javascript:alert" not in html
    assert payload_of(html)["records"][0]["link"] == ""


# --- the payload -------------------------------------------------------------

def test_the_payload_carries_what_the_page_needs_to_filter():
    data = payload_of(build())
    for key in ("records", "unmapped", "facets", "ranges", "bands", "labels",
                "facetFields", "rangeFields", "tableFields", "popupFields",
                "tiles", "csvUrl", "generated", "total"):
        assert key in data, key


def test_unmappable_listings_are_carried_separately_not_dropped():
    data = payload_of(build([row(), row(lat="?", lon="?")]))
    assert len(data["records"]) == 1
    assert len(data["unmapped"]) == 1
    assert data["total"] == 2


def test_filter_options_are_built_from_every_listing_including_unmappable():
    """A filter that hid the unmappable ones would make them unreachable."""
    data = payload_of(build([row(company="A Co"),
                             row(company="B Co", lat="?", lon="?")]))
    assert {o["value"] for o in data["facets"]["company"]} == {"A Co", "B Co"}


def test_every_labelled_field_has_a_label():
    data = payload_of(build())
    for field in data["tableFields"] + data["popupFields"] + data["facetFields"]:
        assert field in data["labels"], field


def test_labels_cover_every_column_the_table_shows():
    assert set(TABLE_FIELDS) <= set(FIELD_LABELS)
    assert set(POPUP_FIELDS) <= set(FIELD_LABELS)


def test_the_address_is_the_popup_heading_and_is_not_repeated_below_it():
    assert "address" not in POPUP_FIELDS


# --- tiles -------------------------------------------------------------------

def test_default_tiles_are_a_known_provider():
    assert DEFAULT_TILES in TILE_PROVIDERS


def test_an_unknown_tile_provider_is_refused_by_name():
    with pytest.raises(ValueError, match="carto-light"):
        build(tiles="nonsense")


@pytest.mark.parametrize("name", sorted(TILE_PROVIDERS))
def test_each_provider_gets_its_own_attribution(name):
    """Esri's cartography is not OSM's; the credit is not interchangeable."""
    data = payload_of(build(tiles=name))
    assert data["tiles"]["attribution"] == TILE_PROVIDERS[name]["attribution"]
    assert data["tiles"]["url"] == TILE_PROVIDERS[name]["url"]


def test_the_suggested_alternative_is_never_the_one_that_just_failed():
    for name in TILE_PROVIDERS:
        assert payload_of(build(tiles=name))["alternative"] != name


def test_the_suggested_alternative_is_never_osm():
    """OSM cannot work from a local file: it requires a Referer."""
    for name in TILE_PROVIDERS:
        assert payload_of(build(tiles=name))["alternative"] != "osm"


# --- the CSV link ------------------------------------------------------------

def test_the_csv_link_points_at_the_published_file_by_default():
    assert payload_of(build())["csvUrl"] == DEFAULT_CSV_URL
    assert DEFAULT_CSV_URL.startswith("https://")


def test_a_non_http_csv_link_is_dropped_rather_than_rendered():
    assert payload_of(build(csv_url="javascript:alert(1)"))["csvUrl"] == ""


def test_the_csv_link_can_be_turned_off():
    assert payload_of(build(csv_url=""))["csvUrl"] == ""


# --- the rest ----------------------------------------------------------------

def test_the_title_is_escaped_in_the_document():
    html = build(title="Rentals & <b>more</b>")
    assert "<b>more</b>" not in html
    assert "&lt;b&gt;more&lt;/b&gt;" in html


def test_the_generated_timestamp_is_shown():
    assert payload_of(build())["generated"] == "2026-09-03 10:30"


def test_an_empty_dataset_still_renders_a_page():
    html = render([], [], generated_at=WHEN)
    assert html.startswith("<!doctype html>")
    assert payload_of(html)["total"] == 0


def test_every_table_column_is_a_field_the_records_carry():
    """A column reading a key no record has would render a column of dashes."""
    from bendrentals.mapdata import RECORD_FIELDS
    assert set(TABLE_FIELDS) <= set(RECORD_FIELDS)


def test_the_map_link_has_no_column_of_its_own():
    """It rides along in the address cell instead."""
    from bendrentals.mapdata import RECORD_FIELDS
    assert "maps_link" in RECORD_FIELDS
    assert "maps_link" not in TABLE_FIELDS


def test_the_listing_link_sits_between_company_and_address():
    assert TABLE_FIELDS.index("company") < TABLE_FIELDS.index("link")
    assert TABLE_FIELDS.index("link") < TABLE_FIELDS.index("address")


def test_property_type_is_not_shown_on_the_page():
    """Only one source publishes it, so the column would be almost all blank.

    It stays in the CSV, where filters.is_residential reads it.
    """
    from bendrentals.mapdata import RECORD_FIELDS
    assert "property_type" not in TABLE_FIELDS
    assert "property_type" not in RECORD_FIELDS
    assert "property_type" in Listing.fieldnames()


def test_cats_and_dogs_are_adjacent_in_the_filters():
    from bendrentals.mapdata import FACET_FIELDS
    order = list(FACET_FIELDS)
    assert abs(order.index("cats_allowed") - order.index("dogs_allowed")) == 1


def test_company_gets_its_own_column_and_leaves_the_main_grid():
    data = payload_of(build())
    assert data["sideFacet"] == "company"
    assert "company" not in data["facetFields"]


def test_the_header_links_to_the_repository():
    html = build()
    assert f'href="{REPO_URL}"' in html
    assert "<svg" in html                       # the mark is inline, not fetched


def test_a_non_http_repo_link_is_dropped():
    assert 'href=""' in build(repo_url="javascript:alert(1)")


def test_the_page_offers_both_jump_links():
    html = build()
    assert 'href="#tablewrap"' in html          # header -> table
    assert 'href="#map"' in html                # table -> map


def test_booleans_are_shown_as_marks_not_as_words():
    data = payload_of(build())
    assert set(data["booleanFields"]) == {"cats_allowed", "dogs_allowed",
                                          "available_now"}


def test_company_is_shown_by_its_short_label():
    """Editing a label in sites.toml and rebuilding is enough to change it."""
    from bendrentals.mapdata import records_from_rows as build_records
    mapped, _ = build_records([row(company="Trailhead Property Management")],
                              {"Trailhead Property Management": "Trailhead"})
    html = render(mapped, [], generated_at=WHEN)
    data = payload_of(html)
    assert data["records"][0]["company"] == "Trailhead"
    assert [o["label"] for o in data["facets"]["company"]] == ["Trailhead"]


def test_a_company_missing_from_the_registry_keeps_its_full_name():
    from bendrentals.mapdata import records_from_rows as build_records
    mapped, _ = build_records([row(company="Gone Property Management")], {})
    assert mapped[0]["company"] == "Gone Property Management"


def test_the_page_points_at_the_favicon_beside_it():
    """Relative, so it resolves on Pages and from a local file alike."""
    from bendrentals.pagehtml import FAVICON
    html = build()
    assert f'<link rel="icon" type="image/png" href="{FAVICON}">' in html
    assert "/" not in FAVICON, "a relative sibling, not a path"
