import pytest

from bendrentals.extract import extract_bathrooms, extract_pets
from bendrentals.models import UNKNOWN

# Real listing text captured 2026-08-31.
DUCK_CALL = (
    "Three bedrooms and HUGE bonus room upstairs. BRAND NEW laminate flooring "
    "downstairs. Private back patio and beautiful front lawn. Quiet street with "
    "easy parkway access. Pets considered with additional deposit."
)
KRISTEN = (
    "Home is in Southwest Pines on an nicely wooded lot. 3 bedrooms, 2.5 baths "
    "and 1924 sq. ft. Granite kitchen counters, a stone fireplace, tiled "
    "bathroom vanities and a great landing area up stairs."
)
BRENTWOOD = (
    "Upscale duplex in great neighborhood. Each 2 story townhouse styled unit "
    "features nice floor plan with 3 bedrooms, 2.5 baths, gas fireplace, open "
    "kitchen, utility room on second floor, gas furnace."
)
RIVERSIDE = (
    "Amazing original historic one bedroom in heart of Bend. 1 block from Drake "
    "Park. One full bedroom with closet, living room, and dining room. Off "
    "street parking lot."
)
MCKINLEY = (
    "2 bedroom 1 bath unit available. Rose Garden Apartments are located close "
    "to the Old Mill, west of HWY 97. No smoking. Upstairs unit coming available."
)


def test_bathrooms_from_description_decimal():
    assert extract_bathrooms(KRISTEN, "Picture2.jpg") == ("2.5", "description")


def test_bathrooms_from_description_before_comma():
    assert extract_bathrooms(BRENTWOOD, "20511.jpg") == ("2.5", "description")


def test_bathrooms_from_description_whole_number():
    assert extract_bathrooms(MCKINLEY, "rose+garden.jpg") == ("1", "description")


def test_bathrooms_falls_back_to_image_filename():
    # Description never says baths; the photo filename encodes "25-bath" = 2.5.
    got = extract_bathrooms(
        DUCK_CALL, "3-br-25-bath-house---19884-duck-call-lane-bend-or.jpg"
    )
    assert got == ("2.5", "image_filename")


def test_bathrooms_unknown_when_neither_source_has_it():
    assert extract_bathrooms(RIVERSIDE, "20230816222115970293000000-o.jpg") == (
        UNKNOWN, "not_found",
    )


def test_bathroom_vanities_alone_is_not_a_count():
    # "tiled bathroom vanities" has no preceding number and must not match.
    assert extract_bathrooms("Nice tiled bathroom vanities.", "x.jpg") == (
        UNKNOWN, "not_found",
    )


@pytest.mark.parametrize("slug,expected", [
    ("3-br-25-bath-house.jpg", "2.5"),   # 2+ digits reads as a decimal
    ("2-br-15-bath.jpg", "1.5"),
    ("2-br-2-bath.jpg", "2"),            # single digit is literal
    ("1-br-1-bath.jpg", "1"),
])
def test_image_filename_decimal_heuristic(slug, expected):
    assert extract_bathrooms("", slug) == (expected, "image_filename")


def test_image_filename_without_bath_token_is_ignored():
    assert extract_bathrooms("", "Building+1+and+2+Aerial.jpeg") == (
        UNKNOWN, "not_found",
    )


def test_trailing_zero_decimal_is_normalised():
    assert extract_bathrooms("Has 2.0 baths.", "x.jpg") == ("2", "description")


def test_pets_returns_the_matching_sentence_verbatim():
    assert extract_pets(DUCK_CALL) == "Pets considered with additional deposit."


@pytest.mark.parametrize("text", [KRISTEN, BRENTWOOD, RIVERSIDE, MCKINLEY])
def test_pets_unknown_when_not_mentioned(text):
    assert extract_pets(text) == UNKNOWN


def test_pets_matches_cat_and_dog_wording():
    assert extract_pets("Great unit. Cats ok, no dogs. Call today.") == (
        "Cats ok, no dogs."
    )


def test_pets_does_not_match_unrelated_no_smoking():
    assert extract_pets("No smoking. Upstairs unit.") == UNKNOWN
