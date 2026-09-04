#!/usr/bin/env python
"""Dump everything every parser reads out of every fixture, as canonical JSON.

    python -m tools.parse_snapshot before.json

Run it either side of a change to the fixtures — a strip, a re-capture, a
hand edit — and diff the two files. An empty diff is proof that the change was
invisible to all five parsers, which the test suite alone cannot tell you:
the tests assert the values they were written to check, and this captures
every value there is.

Files are discovered rather than listed, so adding a fixture needs no edit
here.
"""

import json
import pathlib
import sys

from bs4 import BeautifulSoup

from bendrentals.structures import (
    appfolio_listings, buildium_rentals, prbend_property_pages,
    rentvine_listings, squarespace_portfolio,
)

FIXTURES = pathlib.Path("tests/fixtures")
BASE = "https://example.com"


def _read(path):
    return path.read_text(encoding="utf-8", errors="surrogateescape")


def _soup(path):
    return BeautifulSoup(_read(path), "html.parser")


def _sorted(directory, pattern):
    return sorted(directory.glob(pattern))


def snapshot(root: pathlib.Path = FIXTURES) -> dict:
    """Every value the parsers can extract, keyed by fixture."""
    out = {}

    # --- Squarespace: a title to decode, plus the photo filename that the
    # --- bathroom fallback depends on.
    trailhead = root / "trailhead"
    if (trailhead / "index.html").exists():
        out["trailhead/urls"] = squarespace_portfolio.find_listing_urls(
            _read(trailhead / "index.html"), BASE)
    for path in _sorted(trailhead, "detail*.html"):
        out[f"trailhead/{path.stem}"] = squarespace_portfolio.parse_detail(_read(path))

    # --- AppFolio: every field, straight off the index.
    for path in _sorted(root / "appfolio", "*.html"):
        out[f"appfolio/{path.stem}"] = appfolio_listings.parse_index(_read(path), BASE)

    # --- Buildium. `_description` is included because summary, bathrooms and
    # --- the pet policy are all derived from it.
    buildium = root / "buildium"
    if (buildium / "index.html").exists():
        out["buildium/urls"] = buildium_rentals.find_listing_urls(
            _read(buildium / "index.html"), BASE)
    for path in _sorted(buildium, "detail*.html"):
        out[f"buildium/{path.stem}"] = buildium_rentals.parse_detail_fields(_read(path))
        out[f"buildium/{path.stem}/description"] = buildium_rentals._description(
            _soup(path))

    # --- Preferred Residential.
    prbend = root / "prbend"
    if (prbend / "index.html").exists():
        out["prbend/urls"] = prbend_property_pages.find_listing_urls(
            _read(prbend / "index.html"), BASE)
    for path in _sorted(prbend, "property*.html"):
        out[f"prbend/{path.stem}"] = prbend_property_pages.parse_detail_fields(
            _read(path))
        out[f"prbend/{path.stem}/description"] = prbend_property_pages._description(
            _soup(path))

    # --- Rentvine. Not stripped, being JSON, but checked all the same.
    for path in _sorted(root / "rentvine", "*.json"):
        out[f"rentvine/{path.stem}"] = rentvine_listings.parse_index(
            _read(path), f"{BASE}/api/public/listings")

    return out


def main(argv):
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    if not FIXTURES.exists():
        print(f"No {FIXTURES} here — run this from the repository root.",
              file=sys.stderr)
        return 2

    target = pathlib.Path(argv[0])
    captured = snapshot()
    target.write_text(
        json.dumps(captured, indent=1, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")
    print(f"Wrote {target} ({len(captured)} fixtures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
