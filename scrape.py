#!/usr/bin/env python
"""Scrape rental listings into data/listings.csv.

Usage:
    python scrape.py                    # every ready site in sites.toml
    python scrape.py trailhead          # one site
    python scrape.py superior plus      # several
    python scrape.py --backfill         # geocode at 2s instead of 10s
    python scrape.py --no-geocode       # skip the geocoding step entirely
    python scrape.py --geocode-limit 25 # stop geocoding after 25 new addresses
    python scrape.py --no-snapshot      # skip the dated copy (CI keeps history in git)

Every source writes into the same CSV, distinguished by its `company` column.
Scraping a subset therefore *merges*: the companies you did not ask for, and
any whose site failed, keep the rows they already had.
"""

import sys

from bendrentals.csv_out import merge_rows, read_rows, write_rows
from bendrentals.fetch import BACKFILL_DELAY, FetchError, get
from bendrentals.filters import apply_filters
from bendrentals.geocode import GeocodeCache, geocode_all
from bendrentals.models import UNKNOWN
from bendrentals.registry import LISTINGS_CSV, load_registry, ready_sites
from bendrentals.scraper import ScrapeError, scrape_site

#: Default ceiling on new geocoding lookups per run. Nominatim is rate-limited
#: to well under one request a second here, so an unbounded first run on a wide
#: filter could take hours. Raise it with --geocode-limit for a deliberate
#: catch-up; the cache is permanent, so the rest resolve on later runs.
GEOCODE_LIMIT = 50


def needs_coordinates(listings):
    """Listings without coordinates already supplied by their source."""
    return [l for l in listings if l.lat == UNKNOWN]


def add_coordinates(listings, cache):
    """Fill lat/lon from the cache, leaving source-supplied coordinates alone."""
    for listing in needs_coordinates(listings):
        found = cache.get(listing.address)
        if found:
            listing.lat, listing.lon = found


def _flag_value(argv, name, fallback):
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return argv[index + 1]
    return fallback


def main(argv):
    backfill = "--backfill" in argv
    geocoding = "--no-geocode" not in argv
    snapshot = "--no-snapshot" not in argv
    try:
        limit = int(_flag_value(argv, "--geocode-limit", GEOCODE_LIMIT))
    except ValueError:
        print("--geocode-limit takes a whole number.", file=sys.stderr)
        return 2

    value_flags = {"--geocode-limit"}
    keys = [a for i, a in enumerate(argv)
            if not a.startswith("--") and (i == 0 or argv[i - 1] not in value_flags)]

    settings, sites = load_registry("sites.toml")
    keys = keys or list(ready_sites(sites))

    unknown = [key for key in keys if key not in sites]
    if unknown:
        print(f"Unknown site(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"Available: {', '.join(sites)}", file=sys.stderr)
        return 2

    not_ready = [key for key in keys if not sites[key].is_ready]
    if not_ready:
        print(f"No parser yet for: {', '.join(not_ready)}", file=sys.stderr)
        print("These are candidates in sites.toml.", file=sys.stderr)
        return 2

    failed = False
    scraped = []
    refreshed = set()

    for key in keys:
        site = sites[key]
        print(f"Scraping {site.label} ({site.index_url})")
        try:
            listings = scrape_site(site, get)
        except (FetchError, ScrapeError) as error:
            print(f"ERROR: {site.label}: {error}", file=sys.stderr)
            print("  keeping this company's existing rows", file=sys.stderr)
            failed = True
            continue

        ok = sum(1 for listing in listings if listing.parse_status == "ok")
        print(f"  Parsed {ok}/{len(listings)} listings")
        if ok != len(listings):
            print("  WARNING: some listings parsed only partially", file=sys.stderr)

        listings, dropped = apply_filters(listings, city=settings.city)
        policy = "residential" + (f", {settings.city}" if settings.city else "")
        print(f"  Kept {len(listings)} after filters ({policy}); dropped {dropped}")
        if not listings:
            print("  WARNING: every listing was filtered out", file=sys.stderr)

        scraped.extend(listings)
        refreshed.add(site.company)

    if geocoding and scraped:
        cache = GeocodeCache()
        before = len(cache)
        pending = [l.address for l in needs_coordinates(scraped)]
        new = [a for a in pending if not cache.knows(a)]
        if len(new) > limit:
            print(f"  {len(new)} addresses are new; geocoding {limit} this run "
                  f"(--geocode-limit raises it). The cache is permanent, so the "
                  f"rest resolve on later runs.")
        fetched = geocode_all(
            pending, cache,
            delay=BACKFILL_DELAY if backfill else None,
            limit=limit,
        )
        add_coordinates(scraped, cache)
        missing = sum(1 for l in scraped if l.lat == UNKNOWN)
        print(f"  Geocoded {fetched} new address(es); cache {before} -> {len(cache)}"
              + (f"; {missing} still without coordinates" if missing else ""))

    if not scraped and failed:
        print("Every site failed; data/listings.csv left as it was.", file=sys.stderr)
        return 1

    rows = merge_rows([l.to_row() for l in scraped], refreshed, read_rows(LISTINGS_CSV))
    csv_path, snapshot_path = write_rows(rows, snapshot=snapshot)
    print(f"\nWrote {csv_path}  ({len(rows)} listings from "
          f"{len({r.get('company') for r in rows})} companies)")
    if snapshot_path:
        print(f"Snapshot {snapshot_path}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
