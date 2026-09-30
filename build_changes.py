#!/usr/bin/env python
"""Build LISTING_CHANGES.md from data/listings.csv and its git history.

Usage:
    python build_changes.py                 # writes LISTING_CHANGES.md
    python build_changes.py --days 14       # a longer window
    python build_changes.py --out FILE      # somewhere else
    python build_changes.py --csv FILE      # a different input

The window comes from git, because the published repo keeps no snapshots: the
scheduled workflow's daily commit of the CSV is the history. `changes.py` is
the other tool, and a different one: it reads local snapshots and prints a
report rather than writing a published file.

This step never fails a run. It returns 1 when it could not do its job, and
`update.py` carries on past a 1, because a missing report is not worth losing
a day's listings over.
"""

import csv
import sys
from pathlib import Path

from bendrentals.changelog import build
from bendrentals.csv_out import read_rows
from bendrentals.geocode import DEFAULT_CACHE_PATH, GeocodeCache
from bendrentals.history import GitUnavailable, daily_revisions, rows_at
from bendrentals.registry import LISTINGS_CSV, display_names, load_sites

DEFAULT_OUT = Path("LISTING_CHANGES.md")
DEFAULT_DAYS = 7
REGISTRY = Path("sites.toml")


def flag_value(argv, name, fallback=None):
    """Read `--name value` from a raw argv, returning `fallback` when absent."""
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return argv[index + 1]
    return fallback


def labels(path: Path = REGISTRY) -> dict[str, str]:
    """Company -> short label. Full names are not wrong, only long."""
    try:
        return display_names(load_sites(path))
    except (OSError, ValueError) as error:
        print(f"WARNING: using full company names ({path}: {error})",
              file=sys.stderr)
        return {}


def _history(*, days: int, root: Path) -> tuple[list, str]:
    """(oldest-first [(date, rows)], error message).

    N reported days need N+1 revisions, so this asks for one more than the
    window. An empty list with a message means the caller should still write
    the file and say why the history is missing.

    A single unreadable revision is skipped rather than losing the lot: the
    CSV may not have existed that far back, or a schema change may have made
    it unparseable. Only a failure to list the history at all is total.
    """
    try:
        revisions = daily_revisions(days=days + 1, root=root)
    except GitUnavailable as error:
        return [], str(error)

    past = []
    for date, sha in reversed(revisions):
        try:
            past.append((date, rows_at(sha, root=root)))
        except (GitUnavailable, csv.Error) as error:
            print(f"WARNING: skipping {date} ({sha[:8]}): {error}",
                  file=sys.stderr)
    return past, ""


def main(argv):
    out = Path(flag_value(argv, "--out", DEFAULT_OUT))
    source = Path(flag_value(argv, "--csv", LISTINGS_CSV))

    try:
        days = int(flag_value(argv, "--days", DEFAULT_DAYS))
    except (TypeError, ValueError):
        print("--days takes a whole number.", file=sys.stderr)
        return 2
    if days < 1:
        print("--days must be at least 1.", file=sys.stderr)
        return 2

    if not source.exists():
        print(f"ERROR: no CSV at {source}. Run scrape.py first.", file=sys.stderr)
        return 1
    current = read_rows(source)
    if not current:
        print(f"ERROR: {source} has no listings.", file=sys.stderr)
        return 1

    past, error = _history(days=days, root=Path("."))
    if error:
        print(f"WARNING: no history to compare ({error})", file=sys.stderr)

    try:
        entries = GeocodeCache(DEFAULT_CACHE_PATH).entries
    except (OSError, ValueError) as error:
        print(f"WARNING: unreadable geocode cache ({error})", file=sys.stderr)
        entries = {}

    out.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" explicitly: this file is committed and the scheduled run
    # writes it on Linux, so a Windows build would rewrite every line.
    out.write_text(
        build(past, current, entries, labels=labels(), history_error=error),
        encoding="utf-8", newline="\n",
    )
    print(f"Wrote {out}  ({len(past)} revision(s) of history, "
          f"{len(current)} listings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
