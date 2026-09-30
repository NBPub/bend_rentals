"""data/listings.csv and its git history -> LISTING_CHANGES.md.

Pure rendering. Nothing here reads a file, runs a command or looks at the
clock: it takes rows and returns text. `history.py` does the git work and
`build_changes.py` does the IO, which is what makes this module testable from
plain dicts.

The run date is read out of the data rather than from the clock, so building
twice from the same CSV gives byte-identical text. The file is committed, so
that property is the difference between a clean history and a diff every day.
"""

from datetime import date, timedelta

from .diff import diff_snapshots
from .geocode import FAILURE_RETRY_DAYS
from .models import UNKNOWN

#: Days without a refresh before a company's listings are called stale.
#:
#: The scrape runs daily, and a source that fails keeps its previous rows, so
#: one missed day is noise and three is a pattern worth reading about.
STALE_DAYS = 3


def _day(stamp) -> str:
    """The YYYY-MM-DD part of a scraped_at, or "" if it is not one."""
    text = str(stamp or "")[:10]
    try:
        date.fromisoformat(text)
    except ValueError:
        return ""
    return text


def run_date(rows: list[dict]) -> str:
    """The newest scraped_at date in the file: the date of this run.

    Taken from the data rather than the clock. A file built from a given CSV
    is then always the same file, which a committed artifact needs.
    """
    days = sorted(filter(None, (_day(row.get("scraped_at")) for row in rows)))
    return days[-1] if days else ""


def source_status(rows: list[dict]) -> dict[str, str]:
    """Company -> the newest date any of its rows was scraped.

    A source that failed keeps its previous rows, carrying their old stamp, so
    this is how a failure shows up in the committed data. A source that
    succeeded with no listings leaves the file entirely and is absent here,
    which is what keeps "failed" and "nothing available" apart.
    """
    latest: dict[str, str] = {}
    for row in rows:
        company = row.get("company") or UNKNOWN
        stamp = _day(row.get("scraped_at"))
        if stamp and stamp > latest.get(company, ""):
            latest[company] = stamp
    return latest


def companies_behind(status: dict[str, str], *, today: str,
                     threshold: int = 1) -> dict[str, int]:
    """Company -> days since it last refreshed, for those at or past threshold.

    Serves both the "did not refresh" list (threshold 1) and the stale table
    (threshold STALE_DAYS). A stamp that will not parse is skipped rather than
    raising: an unstamped row is a parse problem to report elsewhere, not a
    reason to lose the whole file.
    """
    if not _day(today):
        return {}
    now = date.fromisoformat(_day(today))
    behind = {}
    for company, stamp in status.items():
        parsed = _day(stamp)
        if not parsed:
            continue
        gap = (now - date.fromisoformat(parsed)).days
        if gap >= threshold:
            behind[company] = gap
    return behind


def geocode_flags(rows: list[dict], cache_entries: dict[str, dict]) -> dict:
    """What is worth saying about geocoding, and nothing more.

    `unmapped` is the listings with no coordinates, which are the ones the
    page lists below the map. `failures` counts the cache's dead ends, and
    `next_retry` is when the oldest of them is tried again.
    """
    unmapped = [
        {"company": row.get("company") or UNKNOWN,
         "address": row.get("address") or UNKNOWN,
         "link": row.get("link") or ""}
        for row in rows if str(row.get("lat", UNKNOWN)) == UNKNOWN
    ]
    failures = [entry for entry in cache_entries.values()
                if str(entry.get("lat", UNKNOWN)) == UNKNOWN]
    dated = sorted(filter(None, (_day(e.get("failed_at")) for e in failures)))
    next_retry = ""
    if dated:
        next_retry = (date.fromisoformat(dated[0])
                      + timedelta(days=FAILURE_RETRY_DAYS)).isoformat()
    return {
        "unmapped": sorted(unmapped, key=lambda u: (u["company"], u["address"])),
        "failures": len(failures),
        "undated_failures": sum(1 for e in failures if not _day(e.get("failed_at"))),
        "next_retry": next_retry,
    }
