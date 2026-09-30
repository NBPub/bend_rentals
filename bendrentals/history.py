"""data/listings.csv as it was on previous days, read out of git.

The published repo keeps no snapshots. The scheduled workflow passes
--no-snapshot deliberately, because its daily commit of data/listings.csv is
the history; `csv_out.py` says so. So the window the changelog reports comes
from `git log` on that one path, and each day's rows from
`git show <sha>:data/listings.csv`.

This is the only module in the package that shells out. Keeping git behind it
is what lets the renderer stay a pure function over dicts, and lets a test
drive either side without the other.
"""

import csv
import io
import subprocess
from pathlib import Path

from .registry import LISTINGS_CSV


class GitUnavailable(Exception):
    """No git, not a repository, or nothing in the history to read.

    Never fatal to a run: the changelog is a reporting nicety, and losing it
    must not cost the day's data. Callers report and carry on.
    """


def _run_git(args: list[str], *, root: Path) -> str:
    """git's stdout as text. Anything that went wrong becomes GitUnavailable."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=str(root), capture_output=True,
            text=True, encoding="utf-8", check=False,
        )
    except (OSError, ValueError) as error:
        raise GitUnavailable(f"cannot run git: {error}") from error
    if done.returncode != 0:
        detail = " ".join((done.stderr or "").split()) or f"exit {done.returncode}"
        raise GitUnavailable(f"git {' '.join(args)}: {detail}")
    return done.stdout


def _repo_path(path: Path | str) -> str:
    """The path as git wants it: repo-relative, forward slashes."""
    return Path(path).as_posix()


def daily_revisions(*, days: int = 7, root: Path | str = Path("."),
                    path: Path | str = LISTINGS_CSV,
                    runner=_run_git) -> list[tuple[str, str]]:
    """(iso date, sha) for the newest commits touching `path`, newest first.

    One entry per commit rather than per calendar day. The scheduled run
    commits once a day so the two coincide in practice; a day with two commits
    contributes two entries, which is harmless because each is compared
    against the one before it.

    `%cs` is the committer date as YYYY-MM-DD, which is what the file reports.
    """
    out = runner(
        ["log", f"-{max(1, int(days))}", "--format=%H %cs",
         "--", _repo_path(path)],
        root=Path(root),
    )
    revisions = []
    for line in out.splitlines():
        sha, _, date = line.strip().partition(" ")
        if sha and date.strip():
            revisions.append((date.strip(), sha))
    return revisions


def rows_at(sha: str, *, root: Path | str = Path("."),
            path: Path | str = LISTINGS_CSV,
            runner=_run_git) -> dict[str, dict]:
    """That revision's rows, keyed by `link`.

    The same shape `diff.read_snapshot` produces, so `diff.diff_snapshots`
    takes it unchanged. A row with no link is dropped: it cannot be matched
    between days, and keeping it would put an empty key in the map.
    """
    text = runner(["show", f"{sha}:{_repo_path(path)}"], root=Path(root))
    reader = csv.DictReader(io.StringIO(text))
    return {row["link"]: row for row in reader if row.get("link")}
