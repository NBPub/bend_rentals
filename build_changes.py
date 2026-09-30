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

from bendrentals.changelog import build, run_date
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

    Asks for one revision more than the window. Reporting N days of movement
    needs N+1 entries, and whether `_with_today` adds one or replaces the
    newest depends on whether this run's commit already exists: in the workflow
    it does not, run again afterwards it does. Fetching the extra and letting
    the caller trim makes the window the same size either way. An empty list
    with a message means the caller should still write the file and say why the
    history is missing.

    A single unreadable revision is kept in the list with None for its rows
    rather than dropped: the CSV may not have existed that far back, or a
    schema change may have made it unmatchable. Dropping it would put two
    non-adjacent revisions side by side and blame one date for two days of
    movement. Only a failure to list the history at all is total.
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
            print(f"WARNING: cannot read {date} ({sha[:8]}): {error}",
                  file=sys.stderr)
            past.append((date, None))
    return past, ""


def _with_today(past: list, current: list[dict]) -> list:
    """`past` plus this run as its newest entry.

    The workflow builds this file *before* committing, so the newest commit is
    yesterday and today's listings exist only in the working tree. Without
    this, the newest dated section would be yesterday's while the header
    asserted today's run date, and today's movement would go unreported.

    Run locally after the day's commit, today is already the newest revision.
    Replace it rather than appending, or the file gains a second section for
    the same date reporting no change against itself.
    """
    today = run_date(current)
    if not today:
        return past
    entry = (today, {row["link"]: row for row in current if row.get("link")})
    if past and past[-1][0] == today:
        return past[:-1] + [entry]
    return past + [entry]


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
    else:
        # Trim to days+1 entries, which is days comparisons. _history fetched
        # one spare because _with_today may add an entry or replace the newest.
        past = _with_today(past, current)[-(days + 1):]

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
    # A 1, not a 0, when there was no history: the file was still written, so
    # nothing is lost, but a silent 0 would let a broken clone depth go
    # unnoticed while the published file quietly said history was missing.
    # update.py carries on past a 1, so the day's data is still committed.
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
