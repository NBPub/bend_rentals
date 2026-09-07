from datetime import datetime
from pathlib import Path

import pytest

from bendrentals.models import UNKNOWN
from bendrentals.registry import Site
from bendrentals.scraper import ScrapeError, build_listing, scrape_site

FIXTURES = Path(__file__).parent / "fixtures" / "trailhead"
SITE = Site(
    key="trailhead", label="Trailhead",
    company="Trailhead Property Management",
    index_url="https://www.trailheadpropertymanagement.com/portfolio-1",
    structure="squarespace_portfolio", title_format="craigslist",
)
NOW = datetime(2026, 8, 31, 14, 22, 7)


def offline_fetcher(url):
    """Serve the captured fixtures instead of hitting the network."""
    if url.endswith("/portfolio-1"):
        return (FIXTURES / "index.html").read_text(encoding="utf-8")
    index = (FIXTURES / "index.html").read_text(encoding="utf-8")
    from bendrentals.structures.squarespace_portfolio import find_listing_urls
    urls = find_listing_urls(index, "https://www.trailheadpropertymanagement.com")
    return (FIXTURES / f"detail{urls.index(url)}.html").read_text(encoding="utf-8")


def test_every_row_is_tagged_with_its_company():
    """One shared CSV, so each row has to say where it came from."""
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    assert {l.company for l in listings} == {"Trailhead Property Management"}


def test_scrapes_all_six_listings():
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    assert len(listings) == 6


def test_every_listing_parses_cleanly():
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    assert all(l.parse_status == "ok" for l in listings)


def test_fields_of_the_first_listing():
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    first = next(l for l in listings if "19884" in l.address)
    assert first.price == 3550
    assert first.bedrooms == 3
    assert first.sqft == 2472
    assert first.region == "SW Bend"
    assert first.address == "19884 Duck Call Lane, Bend OR 97702"
    assert first.summary == "Amazing home in central SW Bend location"
    assert first.pets_raw == "Pets considered with additional deposit."
    assert first.bathrooms == "2.5"
    assert first.maps_link.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert first.scraped_at == "2026-08-31T14:22:07"



def test_measured_pet_sparsity_is_reproduced():
    # Only one of six listings mentions pets at all.
    listings = scrape_site(SITE, offline_fetcher, now=NOW)
    assert sum(1 for l in listings if l.pets_raw != UNKNOWN) == 1


def test_unparseable_title_is_kept_as_partial_not_dropped():
    html = (
        "<html><body><main>"
        "<p>Totally unexpected title text</p>"
        "<p>19884 Duck Call Lane, Bend OR 97702</p>"
        "<p>Some description.</p>"
        "</main></body></html>"
    )
    listing = build_listing(
        "https://example.com/x", html,
        "squarespace_portfolio", "craigslist", "2026-08-31T14:22:07",
    )
    assert listing.parse_status == "partial"
    assert listing.summary == "Totally unexpected title text"
    assert listing.price == UNKNOWN
    assert listing.address == "19884 Duck Call Lane, Bend OR 97702"


def test_zero_listings_is_an_error_not_an_empty_success():
    def empty_fetcher(url):
        return "<html><body>no listings here</body></html>"

    with pytest.raises(ScrapeError, match="No listings"):
        scrape_site(SITE, empty_fetcher, now=NOW)


# --- what "no listings" actually means --------------------------------------

def test_describe_page_names_a_block_page_by_its_title():
    """A refusal and a redesign look identical to the parser, not to this."""
    from bendrentals.scraper import describe_page
    blocked = describe_page(
        "<html><head><title>Just a moment...</title></head><body></body></html>")
    assert "Just a moment" in blocked
    assert "70 bytes" in blocked


def test_describe_page_copes_with_no_title_and_no_page():
    from bendrentals.scraper import describe_page
    assert "no <title>" in describe_page("")
    assert "0 bytes" in describe_page("")


def test_describe_page_collapses_whitespace_in_a_title():
    from bendrentals.scraper import describe_page
    assert "'A Long Title'" in describe_page("<title>A\n  Long   Title</title>")


def test_the_no_listings_error_says_what_arrived():
    """It used to assert the markup had changed, which sent us looking for a
    redesign that had not happened: the host had served a block page."""
    def blocked(url):
        return "<html><head><title>Access denied</title></head><body>no.</body></html>"

    with pytest.raises(ScrapeError) as caught:
        scrape_site(SITE, blocked, now=NOW)

    message = str(caught.value)
    assert "Access denied" in message
    assert "bytes" in message
    assert "probably changed" not in message      # the old, over-confident claim
