"""Writes data/listings.csv plus an identical dated snapshot.

Every source shares one file — the `company` column is what separates them —
so a reader needs no knowledge of the registry to use the data.

Because they share a file, a run that scrapes only some sources must not
delete the rest. `merge_rows` is what makes a partial run safe; the per-site
CSVs this replaced gave that guarantee for free.

The snapshot directory is the local history mechanism that `changes.py` reads.
Published runs get history for free instead: the scheduled workflow commits
`data/listings.csv`, so `git log` on that one path is the record.
"""

import csv
import shutil
from datetime import datetime
from pathlib import Path

from .models import UNKNOWN, Listing
from .registry import LISTINGS_CSV, SNAPSHOT_DIR

#: No colons — they are invalid in Windows filenames.
SNAPSHOT_FORMAT = "%Y-%m-%dT%H%M%S"


def read_rows(path: Path | str) -> list[dict]:
    """Rows of a listings CSV, as dicts keyed by column name. [] if absent."""
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def merge_rows(fresh: list[dict], refreshed: set[str], existing: list[dict]) -> list[dict]:
    """Fresh rows, plus the existing rows of every company not re-scraped.

    `refreshed` names the companies this run actually scraped. Their old rows
    are replaced; everyone else's carry over untouched. A site that was down,
    or that this run simply did not ask for, keeps its previous listings
    rather than disappearing from the file.
    """
    kept = [row for row in existing if row.get("company") not in refreshed]
    return list(fresh) + kept


def carry_first_seen(fresh: list[dict], existing: list[dict], *,
                     today: str) -> int:
    """Fill `first_seen` on fresh rows. Returns how many were newly dated.

    A link already in the previous file keeps the date it had; one never seen
    before takes today's. A known link whose date is "?" stays "?" rather than
    being dated today: it is demonstrably not new, and claiming otherwise
    would make an old listing look like it appeared this morning with no later
    run able to correct it. Those are what `tools/backfill_first_seen.py`
    fills, from the CSV's own commit history.

    Rows that already carry a date are left alone, so the backfill can write
    straight onto the file and survive the next run.
    """
    known = {row.get("link"): row.get("first_seen", UNKNOWN)
             for row in existing if row.get("link")}
    dated = 0
    for row in fresh:
        link = row.get("link")
        if not link or row.get("first_seen", UNKNOWN) != UNKNOWN:
            continue
        if link in known:
            row["first_seen"] = known[link]
        else:
            row["first_seen"] = today
            dated += 1
    return dated


#: Row order in the file. `link` is unique, so this is a total order and the
#: same rows always produce the same file.
SORT_FIELDS = ("company", "address", "link")


def sort_rows(rows: list[dict]) -> list[dict]:
    """A deterministic order, so a diff shows what changed and nothing else.

    Without this the order is scrape order: fresh rows first, then whatever
    `merge_rows` carried over. That is stable only while every site succeeds.
    The run after one site fails would move all of its rows to the end of the
    file, turning a two-line change into a whole-file rewrite — in the file
    whose commit history is supposed to be the record of what changed.
    """
    return sorted(rows, key=lambda row: tuple(
        str(row.get(field, "")) for field in SORT_FIELDS))


def write_rows(
    rows: list[dict],
    *,
    when: datetime | None = None,
    root: Path | str = Path("."),
    snapshot: bool = True,
) -> tuple[Path, Path | None]:
    """Write the combined CSV and, unless asked not to, a timestamped copy."""
    when = when or datetime.now()
    root = Path(root)

    csv_path = root / LISTINGS_CSV
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fields = Listing.fieldnames()
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in sort_rows(rows):
            writer.writerow({name: row.get(name, "") for name in fields})

    if not snapshot:
        return csv_path, None

    snapshot_path = root / SNAPSHOT_DIR / f"{when.strftime(SNAPSHOT_FORMAT)}.csv"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(csv_path, snapshot_path)
    return csv_path, snapshot_path
