#!/usr/bin/env python
"""Build the published page from data/listings.csv.

Usage:
    python build_page.py                       # writes docs/index.html
    python build_page.py --open                # ...and opens it
    python build_page.py --out map.html        # somewhere else
    python build_page.py --csv data/old.csv    # a different input
    python build_page.py --tiles carto-light   # a different tile provider
    python build_page.py --csv-url ""          # drop the download link

The output goes to `docs/` because that is what GitHub Pages serves. It is one
self-contained file with its data baked in: a page opened from `file://` cannot
read a sibling file, so a separate JSON would need a web server just to preview.
"""

import sys
import webbrowser
from pathlib import Path

from bendrentals.csv_out import read_rows
from bendrentals.mapdata import records_from_rows
from bendrentals.pagehtml import (
    DEFAULT_CSV_URL, DEFAULT_TILES, TILE_PROVIDERS, render,
)
from bendrentals.registry import LISTINGS_CSV, display_names, load_sites

DEFAULT_OUT = Path("docs") / "index.html"
TITLE = "Rentals in Bend, OR"
REGISTRY = Path("sites.toml")


def labels(path: Path = REGISTRY) -> dict[str, str]:
    """Company -> short label, for the page's table and company filter.

    Missing or unreadable registry: fall back to the full names in the CSV.
    The page is worth building either way, and the full name is not wrong,
    only long.
    """
    try:
        return display_names(load_sites(path))
    except (OSError, ValueError) as error:
        print(f"WARNING: using full company names ({path}: {error})",
              file=sys.stderr)
        return {}


def flag_value(argv, name, fallback=None):
    """Read `--name value` from a raw argv, returning `fallback` when absent."""
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return argv[index + 1]
    return fallback


def main(argv):
    out = Path(flag_value(argv, "--out", DEFAULT_OUT))
    source = Path(flag_value(argv, "--csv", LISTINGS_CSV))
    tiles = flag_value(argv, "--tiles", DEFAULT_TILES)
    csv_url = flag_value(argv, "--csv-url", DEFAULT_CSV_URL)

    if tiles not in TILE_PROVIDERS:
        print(f"Unknown tile provider {tiles!r}.", file=sys.stderr)
        print(f"Choose one of: {', '.join(sorted(TILE_PROVIDERS))}", file=sys.stderr)
        return 2

    if not source.exists():
        print(f"ERROR: no CSV at {source}. Run scrape.py first.", file=sys.stderr)
        return 1

    rows = read_rows(source)
    if not rows:
        print(f"ERROR: {source} has no listings.", file=sys.stderr)
        return 1

    try:
        mapped, unmapped = records_from_rows(rows, labels())
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" explicitly: the default rewrites every line ending to the
    # platform's. This file is committed, and the scheduled run builds it on
    # Linux, so a Windows build would otherwise show up as a whole-file diff.
    out.write_text(
        render(mapped, unmapped, title=TITLE, tiles=tiles, csv_url=csv_url),
        encoding="utf-8", newline="\n",
    )

    print(f"Wrote {out}  ({len(mapped)} mapped"
          + (f", {len(unmapped)} without coordinates" if unmapped else "") + ")")
    for record in unmapped:
        print(f"  not mappable: {record.get('address') or '(no address published)'}"
              f"  [{record.get('company')}]")

    if "--open" in argv:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
