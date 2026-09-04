import pytest

from bendrentals.formats.craigslist import parse_title

TITLES = [
    ("$3,550 / 3br - 2472ft2 - Amazing home in central SW Bend location (SW Bend)",
     3550, 3, 2472, "Amazing home in central SW Bend location", "SW Bend"),
    ("$3,500 / 3br - 1925ft2 - Great SW Bend Location (SW Bend)",
     3500, 3, 1925, "Great SW Bend Location", "SW Bend"),
    ("$2,150 / 3br - 1357ft2 - Brentwood townhome (SE Bend)",
     2150, 3, 1357, "Brentwood townhome", "SE Bend"),
    ("$1,850 / 1br - 850ft2 - Amazing original historic one bedroom in heart of Bend (Downtown Bend)",
     1850, 1, 850, "Amazing original historic one bedroom in heart of Bend", "Downtown Bend"),
    ("$1,850 / 2br - 850ft2 - Beautifully remodeled condos off Newport in NW Bend (NW Bend)",
     1850, 2, 850, "Beautifully remodeled condos off Newport in NW Bend", "NW Bend"),
    ("$1,675 / 2br - 700ft2 - Newly remodelled apartment in Old Mill (SW Bend)",
     1675, 2, 700, "Newly remodelled apartment in Old Mill", "SW Bend"),
]


@pytest.mark.parametrize("title,price,beds,sqft,summary,region", TITLES)
def test_parses_every_real_title(title, price, beds, sqft, summary, region):
    got = parse_title(title)
    assert got == {
        "price": price, "bedrooms": beds, "sqft": sqft,
        "summary": summary, "region": region,
    }


def test_downtown_region_without_compass_quadrant():
    # "Downtown Bend" has no NE/NW/SE/SW prefix. Region stays one field.
    assert parse_title(TITLES[3][0])["region"] == "Downtown Bend"


def test_price_comma_is_stripped_to_int():
    assert parse_title(TITLES[0][0])["price"] == 3550


def test_summary_containing_parentheses_uses_the_last_group():
    title = "$1,200 / 1br - 500ft2 - Cute (renovated) studio (NE Bend)"
    got = parse_title(title)
    assert got["summary"] == "Cute (renovated) studio"
    assert got["region"] == "NE Bend"


@pytest.mark.parametrize("bad", [
    "Just some random text",
    "",
    "$1,200 / 1br - Cute studio (NE Bend)",          # missing sqft
    "3br - 900ft2 - No price here (SW Bend)",        # missing price
    "$1,200 / 1br - 500ft2 - No region",             # missing parens
])
def test_returns_none_for_unparseable_titles(bad):
    assert parse_title(bad) is None
