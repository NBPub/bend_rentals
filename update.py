#!/usr/bin/env python
"""Run the whole pipeline: scrape, then rebuild the page.

Usage:
    python update.py                       # both steps
    python update.py --skip-scrape         # rebuild the page from the CSV
    python update.py --backfill --open
    python update.py --tiles carto-light

Each step is the same code its own command runs; this only sequences them.
It is what the scheduled workflow calls.

**Failure policy.** The steps share an exit-code contract: 0 fine, 1 something
partial, 2 misconfiguration.

- Exit 2 stops the run. Nothing downstream can work without a usable config.
- Exit 1 warns and carries on. `scrape.py` returns 1 when any one of thirteen
  sites fails, and one site being down is no reason to skip the page for the
  other twelve.
"""

import sys
import time

import build_page
import scrape

#: Flags each step understands. Anything else is passed to no one.
SCRAPE_FLAGS = ("--backfill", "--no-geocode", "--no-snapshot")
SCRAPE_VALUE_FLAGS = ("--geocode-limit",)
PAGE_FLAGS = ("--open",)
PAGE_VALUE_FLAGS = ("--tiles", "--out", "--csv", "--csv-url")

MISCONFIGURED = 2


def _forward(argv, flags=(), value_flags=()):
    """The subset of argv a step should see."""
    out = [arg for arg in argv if arg in flags]
    for flag in value_flags:
        if flag in argv:
            index = argv.index(flag)
            if index + 1 < len(argv):
                out += [flag, argv[index + 1]]
    return out


def _run(name, function, argv):
    """Run one step, timing it and reporting how it went."""
    print(f"\n=== {name} " + "=" * (58 - len(name)))
    started = time.monotonic()
    code = function(argv)
    elapsed = time.monotonic() - started
    status = {0: "ok", 1: "completed with problems"}.get(code, "failed")
    print(f"--- {name}: {status} in {elapsed:.0f}s")
    return code


def main(argv, steps=None):
    steps = steps or {"scrape": scrape.main, "page": build_page.main}
    plan = [
        ("scrape", steps["scrape"], _forward(argv, SCRAPE_FLAGS, SCRAPE_VALUE_FLAGS)),
        ("page", steps["page"], _forward(argv, PAGE_FLAGS, PAGE_VALUE_FLAGS)),
    ]

    worst = 0
    for name, function, step_argv in plan:
        if f"--skip-{name}" in argv:
            print(f"\n=== {name}: skipped")
            continue

        code = _run(name, function, step_argv)
        worst = max(worst, code)

        if code == MISCONFIGURED:
            print(f"\nStopping: {name} is misconfigured.", file=sys.stderr)
            return code

    print("\n" + "=" * 66)
    print({0: "Done.", 1: "Done, with problems reported above."}.get(worst, "Failed."))
    return worst


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
