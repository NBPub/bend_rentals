"""Address -> latitude/longitude.

Providers are tried in order until one answers: Nominatim on the full address,
Nominatim without the unit number (a unit is not a place to OSM, but the
building is), then the US Census geocoder, which knows addresses OSM has not
mapped. Coverage is materially better than Nominatim alone.

Two rules drive the design, both from OSM's usage policy:

1. **Never request the same address twice.** The cache is committed to the
   repository, so a fresh clone geocodes nothing. A resolved address is kept
   for good, because coordinates do not move; a failure is kept only for a
   month, because "not mapped yet" is a statement about today.
2. **Identify the application.** `fetch.py` sends a real User-Agent to both
   geocoders and the vague one everywhere else.

An address no provider can resolve is cached as a failure, but only for a
while: see FAILURE_RETRY_DAYS. A *network* error is not cached at all — it may
be transient.
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote, urlencode

from .fetch import get
from .models import UNKNOWN

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

#: Free US government geocoder. No key, no billing, built for bulk address
#: lookups. Used only after Nominatim misses, which it often resolves — it
#: knows the national address file, including new streets OSM has not mapped.
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
CENSUS_BENCHMARK = "Public_AR_Current"

#: Committed to git — see docs. Rebuilding it means re-crawling Nominatim.
DEFAULT_CACHE_PATH = Path("cache") / "geocode.json"

#: How long a failure is believed before the address is tried again.
#:
#: A success is permanent: the coordinates of a street address do not move.
#: A failure is not. It only ever meant "no provider knows this address yet",
#: which is a statement about today — OpenStreetMap gains streets constantly,
#: and the Census file is revised. Caching that verdict forever means a newly
#: mapped address stays off the map for good, and nothing would ever say so.
#:
#: None of the six addresses currently unresolved recovered on the first
#: retry, so this is insurance rather than a fix for a known case.
#:
#: Thirty days keeps the promise that matters — the same address is not
#: requested twice in a run, or twice in a month — while letting new map data
#: in. An entry with no date predates this and is retried once.
FAILURE_RETRY_DAYS = 30

_PUNCTUATION = str.maketrans({",": " ", ".": " ", "#": " "})


def normalise_address(address: str) -> str:
    """Cache key: case-, spacing- and punctuation-insensitive."""
    if not address or address == UNKNOWN:
        return ""
    return " ".join(address.translate(_PUNCTUATION).lower().split())


class GeocodeCache:
    """Address -> coordinates store, keyed by normalised address.

    Successes are permanent. Failures expire — see FAILURE_RETRY_DAYS.
    """

    def __init__(self, path: Path | str = DEFAULT_CACHE_PATH):
        self.path = Path(path)
        self._entries: dict[str, dict] = {}
        if self.path.exists():
            self._entries = json.loads(self.path.read_text(encoding="utf-8"))

    def knows(self, address: str) -> bool:
        """True if the cache can answer for this address without asking again.

        A stale failure is deliberately *not* known, so it gets another try.
        """
        entry = self._entries.get(normalise_address(address))
        if entry is None:
            return False
        if entry.get("lat", UNKNOWN) != UNKNOWN:
            return True                      # a success, and successes keep
        return not self._failure_is_stale(entry)

    @staticmethod
    def _failure_is_stale(entry: dict) -> bool:
        """Whether a recorded failure is old enough to be worth retrying."""
        when = entry.get("failed_at")
        if not when:
            return True                      # predates the date being recorded
        try:
            failed = date.fromisoformat(when)
        except ValueError:
            return True                      # unreadable, so treat as old
        return date.today() - failed >= timedelta(days=FAILURE_RETRY_DAYS)

    def get(self, address: str) -> tuple[str, str] | None:
        entry = self._entries.get(normalise_address(address))
        if entry is None:
            return None
        return entry.get("lat", UNKNOWN), entry.get("lon", UNKNOWN)

    def put(self, address: str, lat: str, lon: str) -> None:
        key = normalise_address(address)
        if key:
            self._entries[key] = {"lat": lat, "lon": lon, "address": address}

    def put_failure(self, address: str, *, when: date | None = None) -> None:
        """Record that no provider could resolve this, dated so it can expire.

        See FAILURE_RETRY_DAYS: a failure means "not mapped yet", which is a
        statement about today rather than about the address.
        """
        key = normalise_address(address)
        if key:
            self._entries[key] = {
                "lat": UNKNOWN, "lon": UNKNOWN, "address": address,
                "failed_at": (when or date.today()).isoformat(),
            }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordered = dict(sorted(self._entries.items()))
        # newline="\n" explicitly: the default rewrites every line ending to
        # the platform's. This file is committed, and the scheduled run writes
        # it on Linux, so a Windows run would otherwise rewrite all of it.
        self.path.write_text(
            json.dumps(ordered, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )

    def __len__(self) -> int:
        return len(self._entries)


#: Unit designators before the city: " - #2", " #1", " Unit 3", " - B", " Apt 4".
#: Nominatim resolves the building, not the unit, so these cause misses.
#:
#: Note the word boundary after the designators. Bend has a "NE Unity Place",
#: and without it "Unit" matches inside "Unity" — which turns the address into
#: "61073 NE Place" and geocodes it, confidently, to somewhere else entirely.
UNIT_RE = re.compile(
    r"\s*-\s*#?\w+\s*(?=,)"
    r"|\s*#\s*\w+\s*(?=,)"
    r"|\s+(?:Unit|Apt|Apartment|Suite|Ste)\b\.?\s*\S+\s*(?=,)",
    re.IGNORECASE,
)


#: What removing a unit can leave behind. "…, Unit # 2, Bend" loses its number
#: to the "#2" branch above and strands the word; "…, Unit 102, Bend" empties
#: the field and leaves ",,". Both make the fallback query worse than the
#: address it was built from, which is the one thing it must not be.
_STRANDED_RE = re.compile(
    r",\s*(?:Unit|Apt|Apartment|Suite|Ste)\b\.?\s*(?=,)", re.IGNORECASE)
_EMPTY_FIELD_RE = re.compile(r",\s*,")


def street_address(address: str) -> str:
    """Address with any unit designator removed, for a fallback lookup."""
    stripped = re.sub(r"\s+", " ", UNIT_RE.sub(" ", address))
    stripped = stripped.replace(" ,", ",")
    stripped = _STRANDED_RE.sub("", stripped)
    return _EMPTY_FIELD_RE.sub(",", stripped).strip()


def _query_url(address: str) -> str:
    return f"{NOMINATIM_URL}?" + urlencode(
        {"q": address, "format": "jsonv2", "limit": 1}
    )


def _census_url(address: str) -> str:
    return f"{CENSUS_URL}?" + urlencode(
        {"address": address, "benchmark": CENSUS_BENCHMARK, "format": "json"}
    )


def _nominatim_coords(body: str):
    results = json.loads(body)
    if not results:
        return None
    return str(results[0]["lat"]), str(results[0]["lon"])


def _census_coords(body: str):
    matches = json.loads(body).get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    point = matches[0]["coordinates"]
    return str(point["y"]), str(point["x"])


def _providers(address: str):
    """(url, parser) pairs to try in order, cheapest and most-open first."""
    attempts = [(_query_url(address), _nominatim_coords)]
    without_unit = street_address(address)
    if without_unit != address:
        attempts.append((_query_url(without_unit), _nominatim_coords))
    attempts.append((_census_url(address), _census_coords))
    if without_unit != address:
        attempts.append((_census_url(without_unit), _census_coords))
    return attempts


def geocode_all(addresses, cache: GeocodeCache, *, fetcher=get, delay=None,
                limit=None) -> int:
    """Look up every address not already known. Returns how many were resolved.

    Deduplicates within the batch as well as against the cache, so the same
    place is never requested twice even if its text differs between listings.

    `limit` caps how many *new* addresses one run will look up. The cache is
    permanent, so a capped run is not a lost one: the remainder resolve on the
    next run. It exists so an unattended scheduled run cannot turn into an
    hours-long crawl the first time a wide filter finds hundreds of addresses.
    """
    pending = []
    for address in addresses:
        key = normalise_address(address)
        if not key or cache.knows(address):
            continue
        if key not in {normalise_address(a) for a in pending}:
            pending.append(address)

    if limit is not None:
        pending = pending[:limit]

    resolved = 0
    looked_up = False
    for address in pending:
        # In order: Nominatim on the full address, Nominatim without the unit
        # number (a unit is not a place to OSM, but the building is), then the
        # Census geocoder, which knows addresses OSM has not mapped.
        coords = None
        failed = False
        for url, parse in _providers(address):
            try:
                coords = parse(fetcher(url, delay=delay))
            except Exception as error:  # network/decode failure — may be transient
                print(f"WARNING: geocoding failed for {address!r}: {error}")
                failed = True
                break
            looked_up = True
            if coords:
                break

        if failed:
            continue
        if coords:
            cache.put(address, *coords)
            resolved += 1
        else:
            cache.put_failure(address)

    if looked_up:
        cache.save()
    return resolved


#: https://www.google.com/maps/place/<address>/@<lat>,<lon>,<zoom>/...
MAPS_PLACE_RE = re.compile(r"/place/([^/@]+)/@(-?\d+\.\d+),(-?\d+\.\d+)")


def parse_google_maps_place(url: str):
    """(address, lat, lon) from a resolved Google Maps place URL, or None.

    Only reads the URL itself. Nothing about the page is fetched or parsed.
    """
    match = MAPS_PLACE_RE.search(unquote(url or ""))
    if not match:
        return None
    address = match.group(1).replace("+", " ").strip()
    return address, match.group(2), match.group(3)

