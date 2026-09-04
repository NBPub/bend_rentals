from pathlib import Path

import pytest

from bendrentals.models import UNKNOWN
from bendrentals.structures.prbend_property_pages import (
    _description,
    find_listing_urls,
    parse_detail_fields,
)

FIXTURES = Path(__file__).parent / "fixtures" / "prbend"
BASE = "https://prbend.com/bend-long-term-rentals/"


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def soup_of(name):
    from bs4 import BeautifulSoup
    return BeautifulSoup(read(name), "html.parser")


SLUG_FIXTURES = {
    "midtown-bend-with-fenced-yard": "property1.html",
    "northwest-crossing-townhouse": "property2.html",
    "sagewood-house-sw-bend": "property3.html",
    "three-bedroom-townhouse-east-side-bend": "property4.html",
}


def offline_fetcher(url):
    """Serve the index, then each property page matched by its slug."""
    if url == BASE:
        return read("index.html")
    for slug, name in SLUG_FIXTURES.items():
        if slug in url:
            return read(name)
    raise AssertionError(f"unexpected URL: {url}")


def test_finds_the_four_property_links():
    urls = find_listing_urls(read("index.html"), BASE)
    assert len(urls) == 4
    assert all("/property/" in u for u in urls)


def test_excludes_the_bare_property_archive_page():
    # https://prbend.com/property/ is the archive, not a listing.
    urls = find_listing_urls(read("index.html"), BASE)
    assert not any(u.rstrip("/").endswith("/property") for u in urls)


def test_links_are_absolute_and_unique():
    urls = find_listing_urls(read("index.html"), BASE)
    assert all(u.startswith("https://prbend.com/property/") for u in urls)
    assert len(set(urls)) == len(urls)


@pytest.fixture(scope="module")
def sagewood():
    return parse_detail_fields(read("property3.html"))


def test_labelled_fields(sagewood):
    assert sagewood["price"] == 3695
    assert sagewood["bedrooms"] == 3
    assert sagewood["bathrooms"] == "2.5"
    assert sagewood["sqft"] == 2554
    assert sagewood["summary"] == "Sagewood House SW Bend"


def test_price_drops_the_cents(sagewood):
    # The page says "$3,695.00 Per Month".
    assert sagewood["price"] == 3695


def test_region_uses_a_quadrant_from_the_title_when_present(sagewood):
    assert sagewood["region"] == "SW Bend"


def test_region_falls_back_to_the_city_field():
    fields = parse_detail_fields(read("property4.html"))
    # "Three Bedroom Townhouse East Side Bend" states no compass quadrant.
    assert fields["region"] == "Bend"


def test_address_is_unknown_because_the_site_does_not_publish_one(sagewood):
    # The only street address on the page is the agency's own office, taken
    # from the footer map. Using it would put every listing at one false point.
    assert sagewood["address"] == UNKNOWN
    assert "Kearney" not in str(sagewood)


def test_description_is_captured():
    """The body copy is not a stored column, but it is still what we read.

    `summary`, bathrooms and the pet policy all come out of it, so the
    boundaries below still have to hold.
    """
    body = _description(soup_of("property3.html"))
    assert "Sagewood Neighborhood house in SW Bend" in body
    assert "Property Details" not in body


def test_pets_prose_is_captured(sagewood):
    assert "case by case" in sagewood["pets_raw"].lower()


def test_cats_unknown_when_pets_are_merely_considered(sagewood):
    assert sagewood["cats_allowed"] == UNKNOWN


def test_cats_false_when_pets_are_refused_outright():
    fields = parse_detail_fields(read("property2.html"))
    assert "not be considered" in fields["pets_raw"].lower()
    assert fields["cats_allowed"] == "False"


def test_every_fixture_parses_without_error():
    for name in ("property1.html", "property2.html", "property3.html", "property4.html"):
        fields = parse_detail_fields(read(name))
        assert fields["summary"] != UNKNOWN
        assert isinstance(fields["price"], int)


def test_map_link_is_extracted_when_present(sagewood):
    assert sagewood["map_link"].startswith("https://maps.app.goo.gl/")


def test_map_link_is_unknown_when_the_page_has_none():
    fields = parse_detail_fields(read("property4.html"))
    assert fields["map_link"] == UNKNOWN


def test_address_and_coordinates_come_from_the_resolved_map_link():
    from datetime import datetime

    from bendrentals.registry import Site
    from bendrentals.scraper import scrape_site

    site = Site(key="prbend", label="PR", company="Preferred Residential",
                index_url=BASE, structure="prbend_property_pages",
                title_format="structured")
    resolved = ("https://www.google.com/maps/place/61473+Linton+Loop,+Bend,+OR+97702"
                "/@44.033057,-121.339462,17z/data=x")
    listings = scrape_site(site, offline_fetcher, now=datetime(2026, 9, 1),
                           resolver=lambda url: resolved)

    row = next(l for l in listings if "Sagewood" in l.summary)
    assert row.address == "61473 Linton Loop, Bend, OR 97702"
    assert row.lat == "44.033057" and row.lon == "-121.339462"
    # A real address means a working maps link, and no geocoding request.
    assert "Linton+Loop" in row.maps_link


def test_a_listing_without_a_map_link_keeps_an_unknown_address():
    from datetime import datetime

    from bendrentals.registry import Site
    from bendrentals.scraper import scrape_site

    site = Site(key="prbend", label="PR", company="Preferred Residential",
                index_url=BASE, structure="prbend_property_pages",
                title_format="structured")
    listings = scrape_site(site, offline_fetcher, now=datetime(2026, 9, 1),
                           resolver=lambda url: "")

    assert all(l.address == UNKNOWN for l in listings)
    assert all(l.parse_status == "ok" for l in listings)  # absence is not failure


def test_description_stops_before_the_page_footer():
    """It used to run to the end of the document.

    That swept in the footer, putting the agency's postal address and phone
    number into what we read. Fixture contacts are placeholders now, so the
    guard checks the surrounding footer text too.
    """
    body = _description(soup_of("property3.html"))
    for leak in ("555) 555", "Kearney Ave Bend", "Real Estate Investment"):
        assert leak not in body


def test_description_stops_before_the_amenities_checklist():
    for i in range(1, 5):
        description = _description(soup_of(f"property{i}.html"))
        assert "\u2713" not in description, f"property{i} includes the checklist"


def test_available_date_parses_the_month_name_format(sagewood):
    # The page says "Date Available: August 1, 2026".
    assert sagewood["available"] == "2026-08-01"
    assert sagewood["available_now"] == "False"
