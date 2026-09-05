"""CSV rows -> records ready to draw on a map and list in a table.

Pure: no network, no HTML. Every rule about untrusted content lives here, so
the parts that matter are testable offline.

The data comes from thirteen third-party websites and reaches a page that a
browser will execute, so the escaping in `embed_json` is load-bearing, not
decorative.
"""

import json
import re

from .models import UNKNOWN

#: Marker colour by rent, cheapest first. Each band runs up to but not
#: including `below`; the last has no ceiling. Sequential and single-family
#: rather than a red/amber/green traffic light: the colours order listings by
#: price, they do not grade them.
#:
#: Lightness increases monotonically with price, so the ramp survives
#: greyscale printing and the common forms of colour blindness. Change these
#: freely — they are read only from here and from `pagehtml`'s legend.
PRICE_BANDS = (
    {"below": 1000, "label": "under $1,000", "colour": "#c7e9b4"},
    {"below": 1500, "label": "$1,000 - $1,499", "colour": "#7fcdbb"},
    {"below": 2000, "label": "$1,500 - $1,999", "colour": "#41b6c4"},
    {"below": 2500, "label": "$2,000 - $2,499", "colour": "#1d91c0"},
    {"below": 3000, "label": "$2,500 - $2,999", "colour": "#225ea8"},
    {"below": None, "label": "$3,000 and up", "colour": "#0c2c84"},
)

#: A listing whose price could not be read still gets a marker.
UNKNOWN_BAND = {"below": None, "label": "price unknown", "colour": "#9e9e9e"}

#: Columns every row must carry. Missing any of these means the CSV predates a
#: schema change, which is a whole-file problem rather than a per-listing one.
REQUIRED_COLUMNS = ("address", "price", "lat", "lon", "region", "company")

#: Values parsed to numbers, so the page can sort and range-filter them.
NUMERIC_FIELDS = ("price", "bedrooms", "sqft")

#: Columns holding URLs, checked before they are allowed to become clickable.
LINK_FIELDS = ("link", "maps_link")

#: Copied onto each record, in this order. `bathrooms` stays a string because
#: it has to be able to hold "?".
#:
#: `property_type` is deliberately absent: only one source publishes one, so a
#: column of it would be almost entirely blank. It stays in the CSV, where
#: filters.py reads it.
RECORD_FIELDS = (
    "company", "address", "region", "price", "bedrooms", "bathrooms", "sqft",
    "available", "available_now", "cats_allowed", "dogs_allowed", "summary",
    "link", "maps_link",
)

#: Fields offered as tick-box filters, in the order the panel shows them.
#: Cats and dogs sit together because they are read as a pair.
FACET_FIELDS = ("bedrooms", "bathrooms", "cats_allowed", "dogs_allowed",
                "region", "company")

#: Fields offered as a min/max pair.
RANGE_FIELDS = ("price", "sqft")

#: Shown where a value is "?" — the page says so rather than showing a bare
#: question mark, because "the site did not say" is the actual meaning.
UNSTATED = "not stated"

_NUMERIC = re.compile(r"-?\d+(?:\.\d+)?")

#: "NW Bend" -> "Bend". Mirrors place.QUADRANT_RE.
_QUADRANT_PREFIX = re.compile(r"^(?:NE|NW|SE|SW)\s+")

SAFE_URL_SCHEMES = ("http://", "https://")


def number(text):
    """A number from a cell, or None.

    Tolerant of currency and thousands separators: "$1,495.00" is still 1495.
    """
    if text is None:
        return None
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text)
    cleaned = str(text).replace(",", "").strip()
    if not cleaned:
        return None
    match = _NUMERIC.fullmatch(cleaned.lstrip("$"))
    return float(match.group()) if match else None


def price_band(price):
    """The band a rent falls in. An unreadable price still gets one."""
    value = number(price)
    if value is None:
        return UNKNOWN_BAND
    for band in PRICE_BANDS:
        if band["below"] is None or value < band["below"]:
            return band
    return PRICE_BANDS[-1]


def safe_link(value: str) -> str:
    """An http(s) URL, or "" — never a javascript: or data: URL."""
    if not value or value == UNKNOWN:
        return ""
    return value if value.startswith(SAFE_URL_SCHEMES) else ""


def city_of_region(region: str) -> str:
    """"NW Bend" -> "Bend"; "Redmond" -> "Redmond"; "?" -> "?".

    The page uses this to decide that a listing known only to be "in Bend"
    could be in any Bend quadrant, and so must not be hidden when someone
    filters to one.
    """
    if not region or region == UNKNOWN:
        return region or ""
    return _QUADRANT_PREFIX.sub("", region).strip()


def _cell(row, name):
    value = row.get(name)
    return "" if value is None else str(value).strip()


def records_from_rows(rows, display_names=None):
    """Split listing rows into (mappable records, records without coordinates).

    Nothing is dropped: a listing with no coordinates goes in the second list
    rather than being placed at a guess.

    `display_names` maps a full company name to the short label the page
    shows. A company missing from it keeps its full name, so a row from a
    source that has since left the registry is still readable.
    """
    rows = list(rows)
    display_names = display_names or {}
    if rows:
        missing = [name for name in REQUIRED_COLUMNS if name not in rows[0]]
        if missing:
            raise ValueError(
                f"The CSV is missing column(s): {', '.join(missing)}. "
                "It probably predates a schema change — re-run scrape.py."
            )

    mapped, unmapped = [], []
    for row in rows:
        if not any(_cell(row, name) for name in row):
            continue

        record = {}
        for name in RECORD_FIELDS:
            value = _cell(row, name)
            if name in LINK_FIELDS:
                record[name] = safe_link(value)
            elif name in NUMERIC_FIELDS:
                record[name] = number(value)
            else:
                record[name] = "" if value == UNKNOWN else value

        record["company"] = display_names.get(record["company"], record["company"])
        record["band"] = price_band(_cell(row, "price"))

        lat, lon = number(_cell(row, "lat")), number(_cell(row, "lon"))
        if lat is None or lon is None:
            unmapped.append(record)
        else:
            record["lat"], record["lon"] = lat, lon
            mapped.append(record)

    return mapped, unmapped


def facet_value(value) -> str:
    """The string a browser will produce for this value, so the two agree.

    JavaScript has one number type: `String(3.0)` is `"3"`, where Python's
    `str(3.0)` is `"3.0"`. The page matches a record to a tick-box by this
    string, so Python has to write the JavaScript spelling, not its own.
    """
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _facet_key(value: str):
    """Sort numerically where the values are numbers, else alphabetically.

    Bedrooms and bathrooms are numbers, so a plain text sort would put "10"
    before "2". Unstated values sort last, whatever the field.
    """
    if value == "":
        return (2, 0.0, "")
    numeric = number(value)
    return (0, numeric, "") if numeric is not None else (1, 0.0, value.lower())


def facets(records):
    """The tick-box options for each filterable field, in display order.

    Every distinct value present becomes an option, so the page never offers a
    filter that would empty the table, and never hides a value it holds.

    Note `facet_value`, not `or ""`: a studio's bedroom count is 0, and
    treating that as absent would file every studio under "not stated".
    """
    out = {}
    for field in FACET_FIELDS:
        values = sorted({facet_value(record.get(field)) for record in records},
                        key=_facet_key)
        out[field] = [
            {"value": value, "label": value or UNSTATED,
             "city": city_of_region(value) if field == "region" else ""}
            for value in values
        ]
    return out


def ranges(records):
    """The min and max actually present for each range-filtered field.

    Used to set the sliders' bounds. A field with no readable value anywhere
    yields nulls, and the page hides that control rather than showing an
    unusable one.
    """
    out = {}
    for field in RANGE_FIELDS:
        values = [r[field] for r in records if isinstance(r.get(field), (int, float))]
        out[field] = {"min": min(values), "max": max(values)} if values else \
            {"min": None, "max": None}
    return out


#: Characters that end a <script> block or a JS string literal even when they
#: sit inside a quoted JSON value. Mapped to their escaped form. Built with
#: chr(92) so the backslash cannot be mangled by tooling.
_U = chr(92) + 'u'
SCRIPT_UNSAFE = {
    ord('<'): _U + '003c',
    0x2028: _U + '2028',
    0x2029: _U + '2029',
}


def embed_json(data) -> str:
    """JSON safe to place inside a <script> block.

    `json.dumps` alone is not enough. It emits `</script>` verbatim inside a
    string, which closes the block whatever the JSON quoting says, and
    everything after it is parsed as markup. Escaping `<` prevents that and the
    `<!--` case at once. U+2028 and U+2029 terminate a JavaScript string even
    inside quotes, so they go too.
    """
    return json.dumps(data, ensure_ascii=False).translate(SCRIPT_UNSAFE)
