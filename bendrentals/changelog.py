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


def _cell(text) -> str:
    """Table-safe text. A single pipe would otherwise split the row.

    Company labels are human-edited in sites.toml, so this is reachable.
    """
    return str(text or "").replace("|", r"\|").strip()


def _name(row: dict, labels: dict[str, str]) -> str:
    """The company's short label where the registry has one."""
    company = row.get("company") or UNKNOWN
    return labels.get(company, company)


def _entry(row: dict, labels: dict[str, str]) -> str:
    """One listing as a bullet: address linked to the listing, then details."""
    address = row.get("address") or "(no address published)"
    link = row.get("link") or ""
    price = row.get("price") or UNKNOWN
    shown = (f"[{address}]({link})"
             if link.startswith(("http://", "https://")) else address)
    return f"{shown} (${price}, {_name(row, labels)})"


def _one_day(before_date: str, after_date: str, before: dict, after: dict,
             labels: dict[str, str]) -> list[str]:
    """One dated section: a count table, then the listings behind a fold.

    Only additions and removals are reported. `diff_snapshots` also returns
    changed fields, and rendering those would multiply the file's length; a
    column appearing in the CSV would fill it with every listing at once.
    """
    changes = diff_snapshots(before, after)
    added, removed = changes["added"], changes["removed"]
    lines = [f"### {after_date}", ""]

    if not added and not removed:
        lines += [f"No listings added or removed since {before_date}.", ""]
        return lines

    counts: dict[str, list[int]] = {}
    for row in added.values():
        counts.setdefault(_name(row, labels), [0, 0])[0] += 1
    for row in removed.values():
        counts.setdefault(_name(row, labels), [0, 0])[1] += 1

    lines += ["| Company | Added | Removed |", "|---|---:|---:|"]
    for company in sorted(counts):
        gained, lost = counts[company]
        lines.append(f"| {_cell(company)} | {gained} | {lost} |")

    total = len(added) + len(removed)
    lines += ["", "<details>",
              f"<summary>{total} listing{'' if total == 1 else 's'}</summary>", ""]
    for row in sorted(added.values(), key=lambda r: str(r.get("address", ""))):
        lines.append(f"- new: {_entry(row, labels)}")
    for row in sorted(removed.values(), key=lambda r: str(r.get("address", ""))):
        lines.append(f"- gone: {_entry(row, labels)}")
    lines += ["", "</details>", ""]
    return lines


def _changes_section(days, labels, history_error) -> list[str]:
    lines = ["## Recent changes", ""]
    if history_error:
        lines += [f"History was unavailable this run: {history_error}.",
                  "The sections below still describe the current file.", ""]
        return lines
    if len(days) < 2:
        lines += ["Not enough history yet to compare. This needs two committed "
                  "revisions of the CSV to report movement between them.", ""]
        return lines
    for (before_date, before), (after_date, after) in reversed(
            list(zip(days, days[1:]))):
        lines += _one_day(before_date, after_date, before, after, labels)
    return lines


def _sources_section(status, today, labels) -> list[str]:
    behind = companies_behind(status, today=today)
    lines = ["## Sources", ""]
    if not behind:
        lines += [f"All sources refreshed on {today or 'this run'}.", ""]
        return lines
    lines += ["These sources did not answer on this run. Their listings are the "
              "ones they published previously, kept rather than dropped.", "",
              "| Company | Last refreshed | Days behind |", "|---|---|---:|"]
    for company in sorted(behind, key=lambda c: (-behind[c], c)):
        label = labels.get(company, company)
        lines.append(f"| {_cell(label)} | {status[company]} | {behind[company]} |")
    lines.append("")
    return lines


def _geocoding_section(rows, cache_entries) -> list[str]:
    flags = geocode_flags(rows, cache_entries)
    lines = ["## Geocoding", ""]
    if not flags["unmapped"] and not flags["failures"]:
        lines += ["Nothing to flag: every listing has coordinates.", ""]
        return lines

    if flags["unmapped"]:
        lines += [f"{len(flags['unmapped'])} listing(s) have no coordinates and "
                  "are listed below the map rather than placed on it.", "",
                  "| Company | Address |", "|---|---|"]
        for item in flags["unmapped"]:
            lines.append(f"| {_cell(item['company'])} | {_cell(item['address'])} |")
        lines.append("")
    if flags["failures"]:
        detail = f"{flags['failures']} address(es) are cached as unresolved"
        if flags["next_retry"]:
            detail += f"; the oldest is retried on {flags['next_retry']}"
        if flags["undated_failures"]:
            detail += (f". {flags['undated_failures']} predate the retry window "
                       "and are tried again on the next run")
        lines += [detail + ".", ""]
    return lines


def _stale_section(rows, status, today, labels, stale_days) -> list[str]:
    stale = companies_behind(status, today=today, threshold=stale_days)
    lines = ["## Stale listings", ""]
    if not stale:
        lines += [f"No stale listings: nothing has gone {stale_days} days "
                  "without a refresh.", ""]
        return lines
    lines += [f"These have not refreshed for {stale_days} days or more, so "
              "they may no longer be available. Check the listing itself.", "",
              "| Company | Address | Price | Last refreshed |", "|---|---|---|---|"]
    for row in sorted(rows, key=lambda r: (str(r.get("company", "")),
                                           str(r.get("address", "")))):
        company = row.get("company") or UNKNOWN
        if company not in stale:
            continue
        lines.append(
            f"| {_cell(labels.get(company, company))} "
            f"| {_cell(row.get('address') or UNKNOWN)} "
            f"| {_cell(row.get('price') or UNKNOWN)} "
            f"| {status[company]} |")
    lines.append("")
    return lines


def build(days, current, cache_entries, *, labels=None,
          stale_days=STALE_DAYS, history_error="") -> str:
    """The complete LISTING_CHANGES.md text.

    `days` is oldest-to-newest (date, rows keyed by link) and includes this
    run as its last entry, so N reported days need N+1 entries.
    """
    labels = labels or {}
    today = run_date(current)
    status = source_status(current)

    lines = [
        "# Listing changes",
        "",
        "Generated on every scrape by [`build_changes.py`](build_changes.py). "
        "Do not edit: a change made here is gone by morning.",
        "",
        f"Latest run: {today or 'unknown'}. "
        f"{len(current)} listings from {len(status)} companies.",
        "",
        "The complete record is [`data/listings.csv`](data/listings.csv) and its "
        "commit history. This is a readable summary of the last few days of it.",
        "",
    ]
    lines += _changes_section(days, labels, history_error)
    lines += _sources_section(status, today, labels)
    lines += _geocoding_section(current, cache_entries)
    lines += _stale_section(current, status, today, labels, stale_days)
    return "\n".join(lines).rstrip() + "\n"
