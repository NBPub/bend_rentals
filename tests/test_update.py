import pytest

from update import _forward, main


class Recorder:
    """Stands in for a pipeline step, remembering how it was called."""

    def __init__(self, code=0):
        self.code = code
        self.calls = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        return self.code

    @property
    def ran(self):
        return bool(self.calls)


def steps(scrape=0, page=0):
    return {"scrape": Recorder(scrape), "page": Recorder(page)}


def test_runs_both_steps_in_order(capsys):
    plan = steps()
    assert main([], plan) == 0
    assert plan["scrape"].ran and plan["page"].ran
    out = capsys.readouterr().out
    assert out.index("=== scrape") < out.index("=== page")


def test_a_partial_failure_does_not_stop_the_run():
    """One site of thirteen failing is no reason to skip the page."""
    plan = steps(scrape=1)
    assert main([], plan) == 1
    assert plan["page"].ran


def test_misconfiguration_stops_the_run():
    plan = steps(scrape=2)
    assert main([], plan) == 2
    assert not plan["page"].ran


def test_the_worst_exit_code_wins():
    assert main([], steps(scrape=0, page=1)) == 1


@pytest.mark.parametrize("skip", ["scrape", "page"])
def test_either_step_can_be_skipped(skip):
    plan = steps()
    assert main([f"--skip-{skip}"], plan) == 0
    assert not plan[skip].ran
    assert all(step.ran for name, step in plan.items() if name != skip)


def test_scrape_flags_are_forwarded_only_to_scrape():
    plan = steps()
    main(["--backfill", "--no-snapshot"], plan)
    assert plan["scrape"].calls == [["--backfill", "--no-snapshot"]]
    assert plan["page"].calls == [[]]


def test_the_geocode_limit_carries_its_value():
    plan = steps()
    main(["--geocode-limit", "25"], plan)
    assert plan["scrape"].calls == [["--geocode-limit", "25"]]


def test_page_flags_are_forwarded_only_to_the_page():
    plan = steps()
    main(["--open", "--tiles", "carto-light"], plan)
    assert plan["scrape"].calls == [[]]
    assert plan["page"].calls == [["--open", "--tiles", "carto-light"]]


def test_an_unrecognised_flag_is_given_to_nobody():
    plan = steps()
    main(["--nonsense"], plan)
    assert plan["scrape"].calls == [[]]
    assert plan["page"].calls == [[]]


def test_a_value_flag_at_the_end_of_argv_is_dropped_not_crashed():
    assert _forward(["--tiles"], (), ("--tiles",)) == []


def test_each_step_is_timed_and_reported(capsys):
    main([], steps())
    out = capsys.readouterr().out
    assert "--- scrape: ok in" in out
    assert "--- page: ok in" in out
