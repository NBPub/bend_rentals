"""Compare two snapshots and describe what changed, in human terms."""

import csv
from pathlib import Path

from .registry import SNAPSHOT_DIR

#: Changes to these fields are noise, not news. lat/lon move when geocoding
#: improves, not when a listing does -- a better geocoder would otherwise
#: report every listing it newly resolved as "changed".
IGNORED_FIELDS = frozenset({"scraped_at", "lat", "lon"})


def read_snapshot(path: Path | str) -> dict[str, dict]:
    """Load a snapshot CSV keyed by listing link."""
    with open(path, newline="", encoding="utf-8") as handle:
        return {row["link"]: row for row in csv.DictReader(handle)}


def diff_snapshots(old: dict[str, dict], new: dict[str, dict]) -> dict:
    """Return added / removed / changed listings between two snapshots."""
    added = {link: row for link, row in new.items() if link not in old}
    removed = {link: row for link, row in old.items() if link not in new}

    changed = {}
    for link, new_row in new.items():
        if link not in old:
            continue
        old_row = old[link]
        fields = {
            field: (old_row.get(field, ""), value)
            for field, value in new_row.items()
            if field not in IGNORED_FIELDS and old_row.get(field, "") != value
        }
        if fields:
            changed[link] = fields

    return {"added": added, "removed": removed, "changed": changed}


def _label(row: dict) -> str:
    address = row.get("address") or row.get("link", "")
    price = row.get("price", "")
    return f"{address}  (${price})" if price else address


def format_report(diff: dict, old_name: str, new_name: str) -> str:
    """Render a diff as a readable report."""
    lines = [f"Changes from {old_name} to {new_name}", "=" * 60]

    if not any(diff[key] for key in ("added", "removed", "changed")):
        lines.append("No changes.")
        return "\n".join(lines)

    if diff["added"]:
        lines.append(f"\nNEW ({len(diff['added'])})")
        for link, row in diff["added"].items():
            lines.append(f"  + {_label(row)}")
            lines.append(f"      {link}")

    if diff["removed"]:
        lines.append(f"\nGONE ({len(diff['removed'])})")
        for link, row in diff["removed"].items():
            lines.append(f"  - {_label(row)}")
            lines.append(f"      {link}")

    if diff["changed"]:
        lines.append(f"\nCHANGED ({len(diff['changed'])})")
        for link, fields in diff["changed"].items():
            lines.append(f"  ~ {link}")
            for field, (before, after) in fields.items():
                lines.append(f"      {field}: {before!r} -> {after!r}")

    return "\n".join(lines)


def latest_snapshots(*, root: Path | str = Path(".")) -> tuple[Path, Path]:
    """The two most recent snapshots, oldest first.

    Filenames are %Y-%m-%dT%H%M%S, so lexical order is chronological order.
    """
    directory = Path(root) / SNAPSHOT_DIR
    snapshots = sorted(directory.glob("*.csv")) if directory.exists() else []
    if len(snapshots) < 2:
        raise ValueError(
            f"Need at least two snapshots in {directory} to compare; found "
            f"{len(snapshots)}. Published runs keep their history in git "
            f"instead: try `git log -p -- data/listings.csv`."
        )
    return snapshots[-2], snapshots[-1]
