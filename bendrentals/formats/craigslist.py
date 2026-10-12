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

#: The numbers, which are the part worth being strict about. Anything typed
#: before the price is captured rather than skipped: it is lazy, so it stops at
#: the first `$`, and what follows is specific enough that junk cannot match by
#: accident. A title with no `$` at all is still rejected.
TITLE_RE = re.compile(
    r"^(?P<prefix>.*?)\$(?P<price>[\d,]+)\s*/\s*"
    r"(?P<bedrooms>\d+)\s*br\s*-\s*"
    r"(?P<sqft>\d+)\s*ft2\s*-\s*"
    r"(?P<rest>.*)$"
)

#: The region, if the title carries one. Greedy `.*` so a summary with its own
#: parentheses keeps them and only the final group is read as the region:
#: "Cute (renovated) studio (NE Bend)" is summary and region, while
#: "Cute (renovated) studio" is all summary.
REGION_RE = re.compile(r"^(?P<summary>.*)\((?P<region>[^)]*)\)\s*$")


def _kept_prefix(prefix: str) -> str:
    """Text typed before the price, if it is text rather than a slip.

    "Available Now!" is content and belongs in the summary. The `1` of a real
    `1$2,150` is a finger slip and belongs nowhere. A prefix with no letter in
    it is treated as the slip.
    """
    prefix = prefix.strip()
    return prefix if any(char.isalpha() for char in prefix) else ""


def parse_title(title: str) -> dict | None:
    """Parse a Craigslist-style title. Returns None if it does not match.

    A missing region is `UNKNOWN`, not a failure: `"?"` means the source did
    not say it, which is exactly the case here. So is a summary that turns out
    empty, because an empty cell means a bug in this project and this is not
    one.
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

    summary = " ".join(part for part in (_kept_prefix(match["prefix"]), rest)
                       if part)
    return {
        "price": int(match["price"].replace(",", "")),
        "bedrooms": int(match["bedrooms"]),
        "sqft": int(match["sqft"]),
        "summary": summary or UNKNOWN,
        "region": region or UNKNOWN,
    }
