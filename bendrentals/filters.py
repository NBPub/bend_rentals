"""Which listings we keep.

The rule is asymmetric on purpose: **a listing is dropped only when it can be
proven not to qualify.** An unstated property type, an unreadable city, an
unknown bedroom count: all kept. Silently producing fewer rows is the failure
this project exists to prevent, and a broken parser must surface as extra rows
to check, never as missing ones.

Three policies live here.

**Residential rather than commercial.** Two signals, both requiring the source
to have said something:

- a `property_type` naming a commercial use, which only one source publishes;
- a commercial-space phrase in the source's own headline.

The phrase list is deliberately made of two-word nouns rather than bare words.
Of the summaries in a single real run, five mentioned "office", "suite" or
"storage" and only one was a commercial listing: the other four were houses
with a "Bonus Room, Office", a "Loft/office room", and "Storage". Matching
`office` alone would have thrown away four homes to catch one office.

**Something actually for rent.** A stated rent of exactly zero is a source
saying this is not a unit. AppFolio publishes tenant application forms in the
same feed as its listings -- "Use this application to apply as a roommate" --
and prices them $0. Note this tests for a stated zero, never for a missing
price: a markup change yields "?", so it cannot cause a mass drop.

**City**, optional and off unless `sites.toml` sets `city` under `[scrape]`.
It ships set to Bend because that is what the published map covers. Clear it
to keep every city a source lists.
"""

import re

from .models import UNKNOWN
from .place import city_of

#: Property types that are not somewhere to live. Matched as whole words
#: against the source's own `property_type` field, never against free text.
COMMERCIAL_TYPES = frozenset({
    "commercial", "office", "retail", "industrial", "warehouse",
    "storage", "land", "parking",
})

#: Commercial-space phrases in a listing's own headline. Two words each, so a
#: house that merely *has* an office is not mistaken for one. See the module
#: docstring for the real listings that shaped this.
COMMERCIAL_PHRASE_RE = re.compile(
    r"\b(?:"
    r"office\s+(?:suite|space|unit|building)"
    r"|executive\s+suite"
    r"|retail\s+(?:space|unit)"
    r"|commercial\s+(?:space|unit|building|property)"
    r"|warehouse\s+space"
    r"|industrial\s+(?:space|unit)"
    r"|storage\s+unit"
    r"|flex\s+space"
    r")\b",
    re.IGNORECASE,
)

_WORD_RE = re.compile(r"[a-z]+")

#: Hyphens join words in a headline: "Single-Office Suite" is "office suite".
_JOINERS_RE = re.compile(r"[-/]+")


def _stated(value) -> str:
    return "" if value in (None, UNKNOWN) else str(value)


def is_residential(listing) -> bool:
    """False only where the source itself indicates commercial use."""
    stated = _stated(getattr(listing, "property_type", UNKNOWN))
    if stated and set(_WORD_RE.findall(stated.lower())) & COMMERCIAL_TYPES:
        return False

    summary = _JOINERS_RE.sub(" ", _stated(getattr(listing, "summary", "")))
    return not COMMERCIAL_PHRASE_RE.search(summary)


def is_for_rent(listing) -> bool:
    """False only for a listing whose stated rent is exactly zero.

    An unreadable price is not zero, and is kept: this must never be able to
    empty the file when a site changes its markup.
    """
    try:
        # Accepts the int a scrape produces and the text a CSV holds, so the
        # rule reads the same either way.
        value = float(getattr(listing, "price", UNKNOWN))
    except (TypeError, ValueError):
        return True
    return value != 0


def in_city(listing, city: str) -> bool:
    """True unless the listing's address names a different city.

    An address we cannot read is kept: an unparseable address is our problem,
    not evidence the listing is somewhere else.
    """
    if not city:
        return True
    found = city_of(listing.address)
    return found == UNKNOWN or found.lower() == city.lower()


def keeps_listing(listing, *, city: str = "") -> bool:
    """True unless the listing is provably outside what we want."""
    return (is_residential(listing)
            and is_for_rent(listing)
            and in_city(listing, city))


def apply_filters(listings, *, city: str = "") -> tuple[list, int]:
    """Split into (kept, number dropped)."""
    kept = [l for l in listings if keeps_listing(l, city=city)]
    return kept, len(listings) - len(kept)
