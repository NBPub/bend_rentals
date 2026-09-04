import pytest

from bendrentals.filters import (
    COMMERCIAL_TYPES, apply_filters, in_city, is_for_rent, is_residential,
    keeps_listing,
)
from bendrentals.models import UNKNOWN


class Row:
    """Minimal stand-in with just the attributes the filters read."""

    def __init__(self, property_type=UNKNOWN, address="123 Any St, Bend OR 97702",
                 summary="A nice house", price=2495):
        self.property_type = property_type
        self.address = address
        self.summary = summary
        self.price = price


# --- residential: the stated property type ----------------------------------

@pytest.mark.parametrize("stated", ["Single Family", "Condo", "Townhouse",
                                    "Apartment", "Duplex", UNKNOWN, ""])
def test_places_to_live_are_kept(stated):
    assert is_residential(Row(stated)) is True


@pytest.mark.parametrize("stated", ["Commercial", "Office", "Retail Space",
                                    "Industrial", "Warehouse", "Land"])
def test_a_stated_commercial_type_is_dropped(stated):
    assert is_residential(Row(stated)) is False


def test_an_unstated_property_type_is_never_treated_as_commercial():
    """Twelve of thirteen sources publish no property type at all.

    Reading silence as commercial would empty the file.
    """
    assert is_residential(Row(UNKNOWN)) is True


def test_commercial_types_are_matched_as_whole_words():
    # "Landing" begins with a listed word but is somewhere to live.
    assert is_residential(Row("Landing")) is True
    assert "land" in COMMERCIAL_TYPES


# --- residential: the headline ----------------------------------------------
#
# Every string below is from one real run of the thirteen sources.

def test_a_commercial_listing_is_caught_by_its_own_headline():
    """The one commercial listing in the sources, which states no type."""
    assert is_residential(
        Row(summary="Private Single-Office Suite - Downtown Bend")) is False


@pytest.mark.parametrize("summary", [
    "NE House Pet Friendly, 4 Bdrm, 2.5 Bath, Bonus Room, Office, Gas Heat",
    "Great 1 bed/1.5 Bath with Additional Loft/office room in NW Bend!",
    "SE Spacious Upstairs 2 Bedroom Apt w/Air Conditioning, Storage & Parking",
    "Adorable Downtown House, Newer Flooring, A/C, Storage, Fenced Rear Yard",
])
def test_a_home_that_merely_has_an_office_or_storage_is_kept(summary):
    """Matching "office" alone would throw away four homes to catch one office.

    All four of these are real houses from a single run.
    """
    assert is_residential(Row(summary=summary)) is True


@pytest.mark.parametrize("summary", [
    "Retail Space on Wall St", "Downtown Commercial Unit",
    "Warehouse Space with Loading Dock", "Climate-Controlled Storage Unit",
])
def test_other_commercial_headlines_are_caught_too(summary):
    assert is_residential(Row(summary=summary)) is False


def test_a_listing_with_no_headline_is_kept():
    assert is_residential(Row(summary=UNKNOWN)) is True
    assert is_residential(Row(summary="")) is True


# --- something actually for rent --------------------------------------------

@pytest.mark.parametrize("summary", [
    "Application for ADDITIONAL TENANT",
    "Use this application to apply as a roommate",
    "Use this application if you don't see the property you want",
])
def test_application_forms_priced_at_zero_are_not_listings(summary):
    """AppFolio publishes these in the same feed as its rentals, at $0."""
    assert is_for_rent(Row(summary=summary, price=0)) is False


def test_an_unreadable_price_is_not_zero_and_is_kept():
    """This is the whole safety margin: a markup change gives "?", not 0.

    Dropping on a missing price would let one site's redesign empty the file.
    """
    assert is_for_rent(Row(price=UNKNOWN)) is True
    assert is_for_rent(Row(price="")) is True
    assert is_for_rent(Row(price=None)) is True


def test_the_rule_reads_the_same_from_a_scrape_or_from_the_csv():
    """A scrape gives an int; a CSV gives text. Both are the same listing."""
    assert is_for_rent(Row(price=0)) is False
    assert is_for_rent(Row(price="0")) is False
    assert is_for_rent(Row(price="2495")) is True


def test_a_real_rent_is_for_rent():
    assert is_for_rent(Row(price=750)) is True
    assert is_for_rent(Row(price=2495.0)) is True


# --- city -------------------------------------------------------------------

def test_no_city_configured_keeps_everything():
    assert in_city(Row(address="9 A St, Redmond, OR 97756"), "") is True


def test_a_different_city_is_dropped():
    assert in_city(Row(address="9 A St, Redmond, OR 97756"), "Bend") is False


@pytest.mark.parametrize("address", [
    "19884 Duck Call Lane, Bend OR 97702",       # no comma before the state
    "20287 Schaeffer Dr., Bend, OR 97703",       # with one
])
def test_both_address_styles_match_the_city(address):
    assert in_city(Row(address=address), "Bend") is True


def test_an_unreadable_address_is_kept():
    """An address we cannot parse is our problem, not evidence of elsewhere."""
    assert in_city(Row(address=UNKNOWN), "Bend") is True
    assert in_city(Row(address=""), "Bend") is True


def test_the_city_match_ignores_case():
    assert in_city(Row(address="1 A St, BEND, OR 97701"), "bend") is True


# --- all three together -----------------------------------------------------

def test_keeps_listing_requires_all_three():
    assert keeps_listing(Row("Condo"), city="Bend") is True
    assert keeps_listing(Row("Office"), city="Bend") is False
    assert keeps_listing(Row(price=0), city="Bend") is False
    assert keeps_listing(
        Row("Condo", "9 A St, Redmond, OR 97756"), city="Bend") is False


def test_apply_filters_reports_what_it_dropped():
    rows = [
        Row("Single Family"),                                  # kept
        Row(UNKNOWN),                                          # kept: unstated
        Row("Commercial"),                                     # dropped: type
        Row(summary="Private Office Suite"),                   # dropped: headline
        Row(price=0, summary="Roommate application"),          # dropped: not for rent
        Row("Condo", "9 A St, Redmond, OR 97756"),             # dropped: city
    ]
    kept, dropped = apply_filters(rows, city="Bend")
    assert len(kept) == 2
    assert dropped == 4


def test_apply_filters_without_a_city_only_checks_the_other_two():
    rows = [Row("Condo", "9 A St, Redmond, OR 97756"), Row("Office")]
    kept, dropped = apply_filters(rows)
    assert len(kept) == 1
    assert dropped == 1
