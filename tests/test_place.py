import pytest

from bendrentals.models import UNKNOWN
from bendrentals.place import city_of, region_of


@pytest.mark.parametrize("address,expected", [
    # The two address styles our sources actually publish. This module exists
    # because two copies of the pattern disagreed, and one silently failed on
    # the first of these.
    ("19884 Duck Call Lane, Bend OR 97702", "Bend"),
    ("20287 Schaeffer Dr., Bend, OR 97703", "Bend"),
    ("1687 NE 5th St., Redmond, OR 97756", "Redmond"),
    ("100 Main St, Prineville, OR 97754", "Prineville"),
    ("60982 Grand Targhee Drive, Bend, OR 97702", "Bend"),
])
def test_city_is_read_from_either_address_style(address, expected):
    assert city_of(address) == expected


@pytest.mark.parametrize("address", [UNKNOWN, "", "no city here", "Bend"])
def test_an_unreadable_address_yields_unknown(address):
    assert city_of(address) == UNKNOWN


def test_a_quadrant_in_the_first_text_wins():
    assert region_of("Bend", "Duplex in NW Bend", "20287 Schaeffer Dr.") == "NW Bend"


def test_later_texts_are_searched_when_the_first_has_no_quadrant():
    assert region_of("Bend", "Lovely home", "1687 NE 5th St.") == "NE Bend"


def test_the_city_alone_when_no_text_states_a_quadrant():
    assert region_of("Bend", "Lovely home", "60982 Grand Targhee Drive") == "Bend"


def test_a_spelled_out_direction_is_not_a_quadrant():
    """"Northwest Crossing" is a neighbourhood name, not a location claim.

    One listing is called "Northwest Crossing Townhouse" but sits in SE Bend.
    Matching only NE/NW/SE/SW keeps the map from asserting the wrong side.
    """
    assert region_of("Bend", "Northwest Crossing Townhouse") == "Bend"


def test_no_city_means_no_region():
    assert region_of("", "Duplex in NW Bend") == UNKNOWN
    assert region_of(UNKNOWN, "Duplex in NW Bend") == UNKNOWN


def test_unknown_texts_are_skipped_rather_than_matched():
    assert region_of("Bend", UNKNOWN, "", "1687 NE 5th St.") == "NE Bend"


def test_a_quadrant_needs_word_boundaries():
    # "SWALLOW" and "NEWPORT" begin with SW and NE but say nothing about area.
    assert region_of("Bend", "1 SWALLOW Tail Rd") == "Bend"
    assert region_of("Bend", "418 NEWPORT Ave") == "Bend"
