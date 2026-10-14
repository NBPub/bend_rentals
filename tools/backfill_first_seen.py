#!/usr/bin/env python
"""Fill `first_seen` from the CSV's own commit history. Run once.

Usage:
    python -m tools.backfill_first_seen --dry-run
    python -m tools.backfill_first_seen

`first_seen` is derived, so a run can only ever date a listing it has not seen
before. Without this, every listing already in the file would read "?" until
it happened to be re-listed, and the column would be useless for weeks.

The history is already there: the scheduled run commits `data/listings.csv`
daily, so walking those revisions oldest-first and recording the first
revision each `link` appears in reconstructs the column exactly.

**What it cannot know.** A listing present in the oldest revision was already
listed before collection began, so the date it gets is a floor, not a
birthday. That is why the docs call the value "first seen" rather than "listed
on". The proportion shrinks with every run.
"""

import sys
from pathlib import Path

from bendrentals.csv_out import read_rows, sort_rows, write_rows
from bendrentals.history import GitUnavailable, daily_revisions, rows_at
from bendrentals.models import UNKNOWN
from bendrentals.registry import LISTINGS_CSV

#: Far more revisions than exist, so the walk covers all of them.
ALL_REVISIONS = 10_000


def first_appearances(*, root: Path = Path(".")) -> tuple[dict[str, str], str]:
    """link -> the earliest revision date it appears in, and that oldest date.

    Oldest revision first, and `setdefault`, so the first sighting wins.
    """
    revisions = daily_revisions(days=ALL_REVISIONS, root=root)
    if not revisions:
        return {}, ""
    seen: dict[str, str] = {}
    for date, sha in reversed(revisions):          # oldest first
        try:
            rows = rows_at(sha, root=root)
        except GitUnavailable as error:
            print(f"WARNING: skipping {date}: {error}", file=sys.stderr)
            continue
        for link in rows:
            seen.setdefault(link, date)
    return seen, revisions[-1][0]


def main(argv):
    dry_run = "--dry-run" in argv

    try:
        seen, oldest = first_appearances()
    except GitUnavailable as error:
        print(f"ERROR: cannot read the history ({error})", file=sys.stderr)
        return 1
    if not seen:
        print("ERROR: no committed revisions of the CSV to read.", file=sys.stderr)
        return 1

    rows = read_rows(LISTINGS_CSV)
    if not rows:
        print(f"ERROR: no listings in {LISTINGS_CSV}.", file=sys.stderr)
        return 1

    filled, floored, unknown = 0, 0, 0
    for row in rows:
        if row.get("first_seen", UNKNOWN) not in ("", UNKNOWN):
            continue
        found = seen.get(row.get("link", ""))
        if not found:
            unknown += 1
            continue
        row["first_seen"] = found
        filled += 1
        if found == oldest:
            floored += 1

    print(f"{len(rows)} listings; dated {filled}, of which {floored} only to "
          f"{oldest}, the oldest revision — those were already listed before "
          f"collection began and are a floor.")
    if unknown:
        print(f"{unknown} could not be dated: not present in any revision.")

    if dry_run:
        print("--dry-run: nothing written.")
        return 0
    write_rows(sort_rows(rows), snapshot=False)
    print(f"Wrote {LISTINGS_CSV}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
