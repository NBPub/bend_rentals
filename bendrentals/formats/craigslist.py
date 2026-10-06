"""Craigslist-convention title parsing.

    $3,550 / 3br - 2472ft2 - Amazing home in central SW Bend location (SW Bend)
     price    beds   sqft     summary                                  region

This convention appears across unrelated site platforms, which is why it is a
separate axis from the HTML structure module.

The titles are hand-typed on the source site, so the convention is followed
loosely. Two real failures drove the shape of this module: a title that simply
omitted the trailing region, and one that began `1$2,150` because somebody's
finger slipped. The numbers were present and unambiguous in both, so refusing
the whole title cost price, bedrooms and square footage as well as the region.

Hence two patterns rather than one. The trailing region is matched separately
and is optional, which keeps "only a group at the very end is the region" true
without making the whole title conditional on there being one.
"""

import re

from ..models import UNKNOWN

#: The numbers, which are the part worth being strict about. The leading `.*?`
#: skips anything typed before the price: it is lazy, so it stops at the first
#: `$`, and what follows it is specific enough that junk cannot match by
#: accident. A title with no `$` at all is still rejected.
TITLE_RE = re.compile(
    r"^.*?\$(?P<price>[\d,]+)\s*/\s*"
    r"(?P<bedrooms>\d+)\s*br\s*-\s*"
    r"(?P<sqft>\d+)\s*ft2\s*-\s*"
    r"(?P<rest>.*)$"
)

#: The region, if the title carries one. Greedy `.*` so a summary with its own
#: parentheses keeps them and only the final group is read as the region:
#: "Cute (renovated) studio (NE Bend)" is summary and region, while
#: "Cute (renovated) studio" is all summary.
REGION_RE = re.compile(r"^(?P<summary>.*)\((?P<region>[^)]*)\)\s*$")


def parse_title(title: str) -> dict | None:
    """Parse a Craigslist-style title. Returns None if it does not match.

    A missing region is `UNKNOWN`, not a failure: `"?"` means the source did
    not say it, which is exactly the case here.
    """
    if not title:
        return None
    match = TITLE_RE.match(title.strip())
    if not match:
        return None

    rest = match["rest"].strip()
    region = UNKNOWN
    tail = REGION_RE.match(rest)
    if tail:
        rest, region = tail["summary"].strip(), tail["region"].strip()

    return {
        "price": int(match["price"].replace(",", "")),
        "bedrooms": int(match["bedrooms"]),
        "sqft": int(match["sqft"]),
        "summary": rest,
        "region": region or UNKNOWN,
    }
