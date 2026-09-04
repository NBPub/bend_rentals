"""Row shape for scraped listings. Single source of truth for CSV columns."""

from dataclasses import asdict, dataclass, fields
from urllib.parse import quote_plus

#: Written whenever the source site did not state a value. An empty cell
#: therefore always means a bug, never missing source data.
UNKNOWN = "?"

MAPS_SEARCH = "https://www.google.com/maps/search/?api=1&query="


@dataclass
class Listing:
    #: Property management company, from the site's registry entry. Every
    #: listing lands in one shared CSV, so this is what says where it came from.
    company: str
    link: str
    address: str
    region: str
    price: object
    bedrooms: object
    bathrooms: str
    sqft: object
    #: "Single Family", "Condo", ... where the source publishes one. Read by
    #: filters.py, which drops a listing only when this names a commercial use.
    property_type: str
    #: Earliest move-in as an ISO date, or "?". Immediate availability is not a
    #: date, so it lives in `available_now` rather than being invented here.
    available: str
    #: "True" / "False" / "?" — True when the source says the place is ready now.
    available_now: str
    #: "True" / "False" / "?" — sourced from the site, never inferred from
    #: silence. A site that says nothing about cats yields "?", not "False".
    cats_allowed: str
    #: Same rule as cats. A dogs-only policy leaves cats unknown, and a
    #: cats-only policy leaves dogs unknown.
    dogs_allowed: str
    maps_link: str
    #: Geocoded from `address`; "?" until looked up, or supplied by the source.
    lat: str
    lon: str
    #: The source's own headline. Long body copy is deliberately not stored —
    #: it is read during parsing (for bathrooms and pet policy) and discarded.
    summary: str
    pets_raw: str
    scraped_at: str
    parse_status: str

    @classmethod
    def fieldnames(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def to_row(self) -> dict:
        return asdict(self)


def google_maps_link(address: str) -> str:
    """Build a Google Maps search URL using Google's documented stable form."""
    if not address or address == UNKNOWN:
        return UNKNOWN
    return MAPS_SEARCH + quote_plus(address)
