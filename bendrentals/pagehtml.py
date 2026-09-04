"""Map records -> one self-contained HTML page.

The page embeds its data rather than fetching it. A page opened from `file://`
cannot read a sibling file — browsers treat that as cross-origin — so a single
file can be double-clicked and simply works, on GitHub Pages and off it alike.

Nothing here interpolates listing text into markup. Values reach the page only
inside the JSON block that `mapdata.embed_json` has escaped, and the script
writes them with `textContent`, so a listing summary can never become HTML.
Link hrefs are restricted to http(s) in Python before they are ever set.

The document is a template with `__TOKEN__` placeholders rather than an
f-string: the page is mostly CSS and JavaScript, and doubling every brace to
escape it made the source unreadable and the mistakes invisible.
"""

import re
from datetime import datetime
from functools import lru_cache
from html import escape
from pathlib import Path

from .mapdata import (
    FACET_FIELDS, PRICE_BANDS, RANGE_FIELDS, UNKNOWN_BAND, embed_json, facets,
    ranges,
)

LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"

#: Linked from the header icon.
REPO_URL = "https://github.com/NBPub/bend_rentals"

#: Sits beside the page in docs/. Relative, so it resolves both on Pages and
#: when the file is opened directly; writing the page elsewhere with --out
#: simply leaves the browser without an icon.
FAVICON = "favicon.png"

#: Tile providers, keyed by the name `build_page.py --tiles` takes.
#:
#: The default is deliberately not OpenStreetMap's own servers. Their tile
#: usage policy requires a Referer, and a page opened from file:// sends none,
#: so OSM returns a "blocked" image instead of a map. Served over https from
#: GitHub Pages it would work; one default that works everywhere is simpler.
#:
#: Esri and CARTO both work with no key. CARTO renders OSM data (so OSM keeps
#: the credit) but watermarks its free tier; Esri's World Street Map is Esri's
#: own cartography, credited to them alone. Attribution is not interchangeable.
TILE_PROVIDERS = {
    "carto-light": {
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "subdomains": "abcd",
        "attribution": ('&copy; <a href="https://www.openstreetmap.org/copyright">'
                        'OpenStreetMap</a> contributors &copy; '
                        '<a href="https://carto.com/attributions">CARTO</a>'),
    },
    "carto-voyager": {
        "url": "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        "subdomains": "abcd",
        "attribution": ('&copy; <a href="https://www.openstreetmap.org/copyright">'
                        'OpenStreetMap</a> contributors &copy; '
                        '<a href="https://carto.com/attributions">CARTO</a>'),
    },
    "esri": {
        "url": ("https://server.arcgisonline.com/ArcGIS/rest/services/"
                "World_Street_Map/MapServer/tile/{z}/{y}/{x}"),
        "subdomains": "",
        "attribution": "Tiles &copy; Esri",
    },
    # Only usable when the page is served over http(s); see the note above.
    "osm": {
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "subdomains": "abc",
        "attribution": ('&copy; <a href="https://www.openstreetmap.org/copyright">'
                        'OpenStreetMap</a> contributors'),
    },
}

#: Esri by default: no Referer requirement and no watermark.
DEFAULT_TILES = "esri"

#: Column headings, and the labels the filter panel uses for each field.
FIELD_LABELS = {
    "company": "Company",
    "address": "Address",
    "region": "Region",
    "price": "Price",
    "bedrooms": "Beds",
    "bathrooms": "Baths",
    "sqft": "Sq Ft",
    "available": "Available",
    "available_now": "Available now",
    "cats_allowed": "Cats",
    "dogs_allowed": "Dogs",
    "summary": "Summary",
    "link": "Listing",
    "maps_link": "Map",
}

#: Table columns, in order. `maps_link` is absent because the map link is
#: rendered inside the address cell rather than taking a column of its own.
TABLE_FIELDS = (
    "company", "link", "address", "region", "price", "bedrooms", "bathrooms",
    "sqft", "available", "available_now", "cats_allowed", "dogs_allowed",
    "summary",
)

#: Shown in a marker popup when present, in this order. The address is the
#: heading, so it is not repeated here.
POPUP_FIELDS = ("region", "price", "bedrooms", "bathrooms", "sqft",
                "available", "cats_allowed", "dogs_allowed", "company")

#: Rendered as a link rather than as text.
LINK_FIELDS = ("link", "maps_link")

#: Rendered as a tick or a cross rather than the words True and False.
BOOLEAN_FIELDS = ("cats_allowed", "dogs_allowed", "available_now")

#: Given its own column on the right of the filter panel. Thirteen long names
#: crowd the other filters when they share the same grid.
SIDE_FACET = "company"

#: Where the page sends anyone who wants the data rather than the view.
DEFAULT_CSV_URL = (
    "https://raw.githubusercontent.com/NBPub/bend_rentals/main/data/listings.csv"
)


def render(records, unmapped=(), *, generated_at=None, title="Rentals in Bend, OR",
           tiles=DEFAULT_TILES, csv_url=DEFAULT_CSV_URL, repo_url=REPO_URL) -> str:
    """One complete HTML document: map, filters and table."""
    generated_at = generated_at or datetime.now()

    if tiles not in TILE_PROVIDERS:
        raise ValueError(
            f"Unknown tile provider {tiles!r}. "
            f"Choose one of: {', '.join(sorted(TILE_PROVIDERS))}."
        )
    provider = TILE_PROVIDERS[tiles]
    # Suggested in the failure banner; never the one that just failed, and
    # never "osm", which cannot work from a local file at all.
    alternative = next(n for n in TILE_PROVIDERS if n not in (tiles, "osm"))

    records, unmapped = list(records), list(unmapped)
    everything = records + unmapped

    payload = {
        "records": records,
        "unmapped": unmapped,
        "facets": facets(everything),
        "ranges": ranges(everything),
        "bands": list(PRICE_BANDS) + [UNKNOWN_BAND],
        "labels": FIELD_LABELS,
        "facetFields": [f for f in FACET_FIELDS if f != SIDE_FACET],
        "sideFacet": SIDE_FACET,
        "rangeFields": list(RANGE_FIELDS),
        "tableFields": list(TABLE_FIELDS),
        "popupFields": list(POPUP_FIELDS),
        "linkFields": list(LINK_FIELDS),
        "booleanFields": list(BOOLEAN_FIELDS),
        "tiles": provider,
        "alternative": alternative,
        "csvUrl": _safe(csv_url),
        "generated": generated_at.strftime("%Y-%m-%d %H:%M"),
        "total": len(everything),
    }

    return (template()
            .replace("__TITLE__", escape(title))
            .replace("__REPO_URL__", escape(_safe(repo_url), quote=True))
            .replace("__FAVICON__", escape(FAVICON, quote=True))
            .replace("__LEAFLET_CSS__", LEAFLET_CSS)
            .replace("__LEAFLET_JS__", LEAFLET_JS)
            .replace("__PAYLOAD__", embed_json(payload)))


def _safe(url: str) -> str:
    """An http(s) URL, or "". The page renders no link it cannot vouch for."""
    return url if (url or "").startswith(("http://", "https://")) else ""


#: The template, beside this module. Kept as HTML rather than as a string in
#: here so an editor can highlight and check the 500 lines of CSS and
#: JavaScript that make up most of it.
TEMPLATE_PATH = Path(__file__).with_name("page.html")

#: The file opens with a note to whoever edits it. That is for the source, not
#: for the page, so it is dropped on the way through — leaving it in would put
#: a comment above the doctype of every page we publish.
_EDITOR_NOTE_RE = re.compile(r"\A\s*<!--.*?-->\s*", re.S)


@lru_cache(maxsize=1)
def template() -> str:
    """The page template, read once."""
    try:
        raw = TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError as error:
        raise RuntimeError(
            f"Cannot read the page template at {TEMPLATE_PATH}: {error}"
        ) from error
    return _EDITOR_NOTE_RE.sub("", raw)
