#!/usr/bin/env python
"""Summarise what changed between two snapshots.

Usage:
    python changes.py                    # the two most recent snapshots
    python changes.py old.csv new.csv    # two named files

Read-only; it never writes a CSV. Changes to scraped_at, lat and lon are
ignored, because those move without a listing moving.

Snapshots are local: `scrape.py` writes one per run into data/snapshots/, and
that directory is gitignored. A published run keeps its history in git instead,
so on a clone with no snapshots, `git log -p -- data/listings.csv` is the
equivalent.
"""

import sys
from pathlib import Path

from bendrentals.diff import (
    diff_snapshots, format_report, latest_snapshots, read_snapshot,
)


def main(argv):
    paths = [a for a in argv if not a.startswith("--")]

    if len(paths) == 2:
        older, newer = Path(paths[0]), Path(paths[1])
        for path in (older, newer):
            if not path.exists():
                print(f"ERROR: no such file: {path}", file=sys.stderr)
                return 2
    elif paths:
        print("Provide either no snapshot paths, or exactly two.", file=sys.stderr)
        return 2
    else:
        try:
            older, newer = latest_snapshots()
        except ValueError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1

    diff = diff_snapshots(read_snapshot(older), read_snapshot(newer))
    print(format_report(diff, older.name, newer.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
