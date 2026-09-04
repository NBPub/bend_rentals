from pathlib import Path

import pytest

from bendrentals.models import UNKNOWN
from bendrentals.structures.squarespace_portfolio import (
    find_listing_urls,
    parse_detail,
)

FIXTURES = Path(__file__).parent / "fixtures" / "trailhead"
BASE = "https://www.trailheadpropertymanagement.com"


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_finds_all_six_listing_urls():
    urls = find_listing_urls(read("index.html"), BASE)
    assert len(urls) == 6
    assert all(u.startswith(f"{BASE}/portfolio-1/") for u in urls)
    assert len(set(urls)) == 6


def test_listing_urls_are_absolute():
    urls = find_listing_urls(read("index.html"), BASE)
    assert urls[0].startswith("https://")


def test_no_listings_found_returns_empty_list():
    assert find_listing_urls("<html><body>nothing</body></html>", BASE) == []


DETAILS = [
    ("detail0.html", "$3,550 / 3br - 2472ft2 - Amazing home in central SW Bend location (SW Bend)",
     "19884 Duck Call Lane, Bend OR 97702"),
    ("detail1.html", "$3,500 / 3br - 1925ft2 - Great SW Bend Location (SW Bend)",
     "61275 Kristen St, Bend OR 97702"),
    ("detail2.html", "$2,150 / 3br - 1357ft2 - Brentwood townhome (SE Bend)",
     "20511 SE Brentwood, Bend OR 97702"),
    ("detail3.html", "$1,850 / 1br - 850ft2 - Amazing original historic one bedroom in heart of Bend (Downtown Bend)",
     "362 NW Riverside, Bend OR 97703"),
    ("detail4.html", "$1,850 / 2br - 850ft2 - Beautifully remodeled condos off Newport in NW Bend (NW Bend)",
     "1302 NW Knoxville, Bend OR 97703"),
    ("detail5.html", "$1,675 / 2br - 700ft2 - Newly remodelled apartment in Old Mill (SW Bend)",
     "35 SW McKinley, Bend OR 97702"),
]


@pytest.mark.parametrize("name,title,address", DETAILS)
def test_parses_title_and_address_from_every_detail_page(name, title, address):
    got = parse_detail(read(name))
    assert got["title"] == title
    assert got["address"] == address


def test_description_excludes_title_and_address():
    got = parse_detail(read("detail0.html"))
    assert got["description"].startswith("Three bedrooms and HUGE bonus room")
    assert "19884 Duck Call Lane" not in got["description"]
    assert "$3,550" not in got["description"]


def test_description_joins_all_remaining_paragraphs():
    got = parse_detail(read("detail0.html"))
    assert "Pets considered with additional deposit." in got["description"]
    assert "Tenant pays all utilities." in got["description"]


def test_description_excludes_navigation_chrome():
    got = parse_detail(read("detail0.html"))
    assert "Request an Application" not in got["description"]
    assert not got["description"].rstrip().endswith("Next")


def test_image_filename_is_url_decoded():
    # unquote decodes %28/%29 to parentheses but leaves "+" alone (that is
    # unquote_plus's job), so the "+" before "(1)" survives verbatim.
    got = parse_detail(read("detail0.html"))
    assert got["image_filename"] == (
        "3-br-25-bath-house---19884-duck-call-lane-bend-or-building-photo+(1).jpg"
    )


def test_missing_address_yields_unknown_not_crash():
    html = "<html><body><main><p>Some title</p><p>Some body.</p></main></body></html>"
    got = parse_detail(html)
    assert got["address"] == UNKNOWN
    assert got["title"] == "Some title"


def test_empty_main_yields_unknowns():
    got = parse_detail("<html><body><main></main></body></html>")
    assert got["title"] == UNKNOWN
    assert got["address"] == UNKNOWN
    assert got["description"] == UNKNOWN
