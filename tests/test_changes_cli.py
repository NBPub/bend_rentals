import csv

import pytest

from bendrentals.models import Listing
from changes import main


def snapshot(path, price="2495"):
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict.fromkeys(Listing.fieldnames(), "?")
    row.update(link="https://example.com/1", price=price, bedrooms="3",
               company="Trailhead Property Management",
               address="1 A St, Bend, OR 97701", parse_status="ok")
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=Listing.fieldnames())
        writer.writeheader()
        writer.writerow(row)


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def snapshots(project):
    return project / "data" / "snapshots"


def test_reports_a_change_between_the_two_most_recent(project, capsys):
    snapshot(snapshots(project) / "2026-09-01T090000.csv", price="2495")
    snapshot(snapshots(project) / "2026-09-02T090000.csv", price="2395")
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "2495" in out and "2395" in out


def test_says_so_when_nothing_changed(project, capsys):
    snapshot(snapshots(project) / "2026-09-01T090000.csv")
    snapshot(snapshots(project) / "2026-09-02T090000.csv")
    main([])
    assert "No changes" in capsys.readouterr().out


def test_explicit_files_can_be_given(project, capsys):
    older, newer = project / "a.csv", project / "b.csv"
    snapshot(older, price="2495")
    snapshot(newer, price="1995")
    assert main([str(older), str(newer)]) == 0
    assert "1995" in capsys.readouterr().out


def test_one_snapshot_is_not_enough_to_compare(project, capsys):
    snapshot(snapshots(project) / "2026-09-01T090000.csv")
    assert main([]) == 1
    assert "at least two" in capsys.readouterr().err


def test_with_no_snapshots_it_points_at_git(project, capsys):
    """A fresh clone has none: the published history lives in git instead."""
    assert main([]) == 1
    assert "git log" in capsys.readouterr().err


def test_exactly_one_path_is_rejected(project, capsys):
    """Two snapshots or none; one is a mistake worth naming."""
    snapshot(project / "a.csv")
    assert main([str(project / "a.csv")]) == 2
    assert "exactly two" in capsys.readouterr().err


def test_a_missing_file_is_named_rather_than_traced(project, capsys):
    snapshot(project / "a.csv")
    assert main([str(project / "a.csv"), str(project / "gone.csv")]) == 2
    assert "gone.csv" in capsys.readouterr().err
