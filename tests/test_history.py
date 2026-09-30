import csv
import os
import subprocess
from pathlib import Path

import pytest

from bendrentals.history import GitUnavailable, daily_revisions, rows_at

FIELDS = ["company", "link", "address", "price", "scraped_at", "lat"]


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row.get(f, "") for f in FIELDS})


def git(repo: Path, *args, when=None):
    """Run git in `repo`. `when` fixes both dates, so %cs is predictable."""
    env = None
    if when:
        env = {**os.environ,
               "GIT_AUTHOR_DATE": f"{when}T12:00:00",
               "GIT_COMMITTER_DATE": f"{when}T12:00:00"}
    done = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                          text=True, check=True, env=env)
    return done.stdout


@pytest.fixture
def repo(tmp_path):
    """A throwaway repo with three daily commits of data/listings.csv.

    Local git only. No network, so this keeps the offline guarantee.
    """
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    csv_path = root / "data" / "listings.csv"

    for day, rows in [
        ("2026-01-01", [{"company": "A", "link": "L1", "address": "One"}]),
        ("2026-01-02", [{"company": "A", "link": "L1", "address": "One"},
                        {"company": "A", "link": "L2", "address": "Two"}]),
        ("2026-01-03", [{"company": "A", "link": "L2", "address": "Two"}]),
    ]:
        write_csv(csv_path, rows)
        git(root, "add", "data/listings.csv")
        git(root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", f"day {day}",
            when=day)
    return root


def test_revisions_are_newest_first(repo):
    found = daily_revisions(days=7, root=repo)
    assert len(found) == 3
    dates = [date for date, _ in found]
    assert dates == sorted(dates, reverse=True)


def test_revisions_respect_the_window(repo):
    assert len(daily_revisions(days=2, root=repo)) == 2


def test_rows_at_reads_that_revisions_file(repo):
    revisions = daily_revisions(root=repo)
    newest_sha = revisions[0][1]
    oldest_sha = revisions[-1][1]
    assert set(rows_at(newest_sha, root=repo)) == {"L2"}
    assert set(rows_at(oldest_sha, root=repo)) == {"L1"}


def test_a_row_with_no_link_is_dropped(repo):
    """Review Focus 2: an unlinked row would otherwise become a "" key."""
    def runner(args, *, root):
        return ("company,link,address\n"
                "A,,No link here\n"
                "A,L9,Has one\n")
    assert set(rows_at("whatever", root=repo, runner=runner)) == {"L9"}


def test_a_duplicated_link_keeps_one_row(repo):
    """Review Focus 2: duplicates must not raise; last one wins."""
    def runner(args, *, root):
        return ("company,link,address\n"
                "A,L1,First\n"
                "A,L1,Second\n")
    rows = rows_at("whatever", root=repo, runner=runner)
    assert list(rows) == ["L1"]
    assert rows["L1"]["address"] == "Second"


def test_not_a_repository_raises_git_unavailable(tmp_path):
    with pytest.raises(GitUnavailable):
        daily_revisions(root=tmp_path)


def test_a_missing_git_binary_raises_git_unavailable(repo, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("git not found")
    monkeypatch.setattr("bendrentals.history.subprocess.run", boom)
    with pytest.raises(GitUnavailable, match="cannot run git"):
        daily_revisions(root=repo)


def test_a_revision_without_a_link_column_is_refused(repo):
    """Review Focus 4, the renamed-column half.

    Filtering every row out would make the revision look empty, and the
    changelog would report a full turnover: everything removed, then re-added.
    """
    def runner(args, *, root):
        return "company,url,address\nA,https://x/1,Somewhere\n"
    with pytest.raises(GitUnavailable, match="link"):
        rows_at("whatever", root=repo, runner=runner)
