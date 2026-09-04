from datetime import datetime
from pathlib import Path

from bendrentals.filters import apply_filters
from bendrentals.models import UNKNOWN
from bendrentals.registry import Site
from bendrentals.scraper import scrape_site

FIXTURES = Path(__file__).parent / "fixtures" / "appfolio"
SITE = Site(
    key="mountain_view", label="Mountain View",
    company="Mountain View Property Management",
    index_url="https://mountainviewpm.appfolio.com/listings",
    structure="appfolio_listings", title_format="structured",
)
NOW = datetime(2026, 9, 1, 9, 0, 0)


def offline_fetcher(url):
    return (FIXTURES / "index_all.html").read_text(encoding="utf-8")


def test_structured_site_needs_only_the_index_request():
    calls = []

    def counting(url):
        calls.append(url)
        return offline_fetcher(url)

    listings = scrape_site(SITE, counting, now=NOW)
    assert len(listings) == 16
    assert len(calls) == 1, "AppFolio must not fetch a page per listing"


def test_fields_survive_into_listings():
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    row = next(l for l in listings if "Schaeffer" in l.address)
    assert row.price == 2395
    assert row.bedrooms == 3
    assert row.bathrooms == "2.5"
    assert row.sqft == 1485
    assert row.region == "NW Bend"
    # This listing's policy mentions dogs only, so cats stay unknown.
    assert row.pets_raw == "Small dogs allowed"
    assert row.cats_allowed == UNKNOWN
    assert row.maps_link.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert row.parse_status == "ok"
    assert row.scraped_at == "2026-09-01T09:00:00"


def test_lat_lon_start_unknown_and_are_filled_in_later():
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    assert all(l.lat == UNKNOWN and l.lon == UNKNOWN for l in listings)


def test_cats_allowed_is_populated_for_most_listings():
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    known = [l for l in listings if l.cats_allowed != UNKNOWN]
    assert len(known) == 14  # 12 True + 2 False, 2 unstated


def test_dogs_are_read_alongside_cats():
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    row = next(l for l in listings if "Schaeffer" in l.address)
    # "Small dogs allowed" — dogs yes, and cats still genuinely unknown.
    assert row.dogs_allowed == "True"
    assert row.cats_allowed == UNKNOWN


def test_appfolio_states_no_property_type():
    """Nine of thirteen sources are AppFolio, and none says what a unit is.

    filters.is_residential therefore has to keep every one of them.
    """
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    assert all(l.property_type == UNKNOWN for l in listings)


def test_source_filtered_page_still_passes_our_own_filters():
    # The fixture was fetched with the source's Bend filter applied, so the
    # local safety net should drop nothing.
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    kept, dropped = apply_filters(listings, city="Bend")
    assert dropped == 0
    assert len(kept) == 16
