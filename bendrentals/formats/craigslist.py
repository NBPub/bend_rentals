"""Craigslist-convention title parsing.

    $3,550 / 3br - 2472ft2 - Amazing home in central SW Bend location (SW Bend)
     price    beds   sqft     summary                                  region

This convention appears across unrelated site platforms, which is why it is a
separate axis from the HTML structure module.
"""

import re

TITLE_RE = re.compile(
    r"^\$(?P<price>[\d,]+)\s*/\s*"
    r"(?P<bedrooms>\d+)\s*br\s*-\s*"
    r"(?P<sqft>\d+)\s*ft2\s*-\s*"
    r"(?P<summary>.*)"
    r"\((?P<region>[^)]*)\)\s*$"
)


def parse_title(title: str) -> dict | None:
    """Parse a Craigslist-style title. Returns None if it does not match."""
    if not title:
        return None
    match = TITLE_RE.match(title.strip())
    if not match:
        return None
    return {
        "price": int(match["price"].replace(",", "")),
        "bedrooms": int(match["bedrooms"]),
        "sqft": int(match["sqft"]),
        "summary": match["summary"].strip(),
        "region": match["region"].strip(),
    }
