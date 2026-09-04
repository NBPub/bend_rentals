from pathlib import Path

import pytest

from bendrentals.models import UNKNOWN
from bs4 import BeautifulSoup

from bendrentals.structures.buildium_rentals import (
    _description,
    find_listing_urls,
    parse_detail_fields,
)

FIXTURES = Path(__file__).parent / "fixtures" / "buildium"
BASE = "https://hummingbirdpropertymanagement.managebuilding.com/Resident/public/rentals"


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def soup_of(name):
    return BeautifulSoup(read(name), "html.parser")


def test_finds_every_rental_detail_url():
    urls = find_listing_urls(read("index.html"), BASE)
    assert len(urls) == 7
    assert all("/Resident/public/rentals/" in u for u in urls)


def test_excludes_the_index_itself_and_the_application_link():
    urls = find_listing_urls(read("index.html"), BASE)
    assert not any(u.rstrip("/").endswith("/rentals") for u in urls)
    assert not any("rental-application" in u for u in urls)


def test_urls_are_absolute_and_unique():
    urls = find_listing_urls(read("index.html"), BASE)
    assert all(u.startswith("https://") for u in urls)
    assert len(set(urls)) == len(urls)


@pytest.fixture(scope="module")
def targhee():
    return parse_detail_fields(read("detail0.html"))


def test_address_joins_the_two_heading_lines(targhee):
    assert targhee["address"] == "60982 Grand Targhee Drive, Bend, OR 97702"


def test_numeric_fields(targhee):
    assert targhee["price"] == 2595
    assert targhee["bedrooms"] == 3
    assert targhee["bathrooms"] == "2.5"
    assert targhee["sqft"] == 1525


def test_price_drops_the_cents_and_the_per_month_suffix(targhee):
    # The page says "$2,595.00 / month".
    assert targhee["price"] == 2595


def test_region_is_the_city_when_the_address_states_no_quadrant(targhee):
    # This address has no NE/NW/SE/SW. The description says "SE Bend", but a
    # description mentioning a neighbourhood is not evidence the property is in
    # it ("close to NW Crossing"), so region is not mined from prose.
    assert targhee["region"] == "Bend"


def test_region_picks_up_a_quadrant_when_the_address_has_one():
    regions = {parse_detail_fields(read(f"detail{i}.html"))["region"] for i in range(7)}
    assert any(r.startswith(("NE ", "NW ", "SE ", "SW ")) for r in regions)


def test_description_is_captured():
    """The body copy is not a stored column, but summary and pets come from it."""
    body = _description(soup_of("detail0.html"))
    assert body.startswith("Lovely home in newer subdivision")


def test_summary_is_the_opening_sentence_not_the_address(targhee):
    """Buildium publishes no headline; its only title is the street address.

    Using that made summary a duplicate of the address column.
    """
    assert targhee["summary"] == (
        "Lovely home in newer subdivision in SE Bend not far from Murphy and Parrell Roads."
    )
    assert targhee["summary"] not in targhee["address"]


def test_every_summary_reads_like_a_headline():
    for i in range(7):
        fields = parse_detail_fields(read(f"detail{i}.html"))
        assert fields["summary"] != UNKNOWN
        assert fields["summary"] not in fields["address"]
        assert len(fields["summary"]) < 200


def test_pet_policy_is_captured_from_the_detail_page():
    # The index carries no pet information at all; the detail page does.
    found = [parse_detail_fields(read(f"detail{i}.html")) for i in range(7)]
    with_pets = [f for f in found if f["pets_raw"] != UNKNOWN]
    assert with_pets, "expected at least one listing to state a pet policy"


def test_every_fixture_parses_with_a_price_and_address():
    for i in range(7):
        fields = parse_detail_fields(read(f"detail{i}.html"))
        assert isinstance(fields["price"], int), i
        assert fields["address"] != UNKNOWN, i
        assert "Bend" in fields["address"], i


def test_one_bedroom_listing_is_present_for_the_filter_to_drop():
    # Buildium offers no source-side bedroom filter, so ours must do the work.
    beds = [parse_detail_fields(read(f"detail{i}.html"))["bedrooms"] for i in range(7)]
    assert 1 in beds


def test_description_joins_every_block():
    """Pages carry two .unit-detail__description elements.

    Taking only the first lost 97% of the text on one listing and 32% on
    another; the rest have an empty second block, so joining is safe.
    """
    body = _description(soup_of("detail2.html"))
    assert len(body) > 800
    assert "Newly renovated" in body
    assert body.startswith("2 Unit multi-family home")


def test_available_date_is_iso(targhee):
    # The page says "Available 10/20/2026".
    assert targhee["available"] == "2026-10-20"
    assert targhee["available_now"] == "False"
