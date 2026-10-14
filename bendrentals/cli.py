"""Reading `--flag value` out of a raw argv.

Three entry points had grown their own identical copy of this, and all three
shared the same defect: a flag present with nothing usable after it fell back
to the default and said nothing. `--days=14` was read as the default 7, and a
trailing `--days` likewise, so the command answered a question nobody asked.

The scripts take argv directly rather than through argparse because
`update.py` forwards a subset of its own flags to each step, and argparse
wants to own the whole command line.
"""


class FlagError(ValueError):
    """A flag was given without a usable value.

    Raised rather than falling back, because the fallback is a different
    answer from the one asked for and silence about that is the bug.
    """


def flag_value(argv, name, fallback=None):
    """Read `--name value` or `--name=value`. `fallback` when absent."""
    prefix = f"{name}="
    for index, arg in enumerate(argv):
        if arg.startswith(prefix):
            value = arg[len(prefix):]
            if not value:
                raise FlagError(f"{name} needs a value, as {name}=VALUE.")
            return value
        if arg == name:
            if index + 1 < len(argv):
                return argv[index + 1]
            raise FlagError(f"{name} needs a value after it.")
    return fallback
