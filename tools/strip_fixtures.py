#!/usr/bin/env python
"""Strip the parts of a saved fixture that no parser reads.

    python -m tools.strip_fixtures            # every stage
    python -m tools.strip_fixtures padding    # one stage, by name

A captured Squarespace or Divi page is mostly framework: bundled JavaScript,
stylesheets, base64 image payloads, a dozen CDN variants of every photo, and
runs of hundreds of spaces. None of it is content, and all of it would sit in
git history forever. Stripping took the fixture set from 4.4 MB to 1.1 MB
without changing a single parsed value.

**Always verify with `tools.parse_snapshot`**, which is what makes this safe:

    python -m tools.parse_snapshot before.json
    python -m tools.strip_fixtures
    python -m tools.parse_snapshot after.json
    diff before.json after.json          # must be empty

Every transformation works on the raw text. Re-serialising through
BeautifulSoup would rewrite the whole document and could change parse results
by itself, which is exactly what the diff is meant to detect.
"""

import pathlib
import re
import sys

FIXTURES = pathlib.Path("tests/fixtures")

SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.S | re.I)
STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.S | re.I)

#: Only the payload. The attribute, its scheme and its media type all stay, so
#: anything reading the URL still sees a data: URI rather than a filename.
BASE64_RE = re.compile(r"(data:[^;\"'\s]*;base64,)[A-Za-z0-9+/=%]{64,}")

#: Responsive-image attributes. `squarespace_portfolio` reads `data-src` or
#: `src` for a photo filename; nothing reads srcset or sizes.
SRCSET_RE = re.compile(r"""\s+(?:srcset|sizes|imagesrcset)=("[^"]*"|'[^']*')""", re.I)

#: Squarespace pads its pages with runs of hundreds of spaces — 820 KB of one
#: fixture. Sixteen is far past anything meaningful, and every parser
#: normalises whitespace before reading a value.
PADDING_RE = re.compile(r"[ \t]{16,}")

BLANKS_RE = re.compile(r"\n[ \t]*(?:\n[ \t]*)+")

#: In order. Names are the arguments this accepts on the command line.
STAGES = (
    ("scripts", lambda text: SCRIPT_RE.sub("", text)),
    ("styles", lambda text: STYLE_RE.sub("", text)),
    ("base64", lambda text: BASE64_RE.sub(r"\1STRIPPED", text)),
    ("srcset", lambda text: SRCSET_RE.sub("", text)),
    ("padding", lambda text: PADDING_RE.sub(" ", text)),
    ("blanks", lambda text: BLANKS_RE.sub("\n", text)),
)


def strip(text: str, only=None) -> str:
    """Apply every stage, or only the named ones."""
    for name, transform in STAGES:
        if only is None or name in only:
            text = transform(text)
    return text


def main(argv):
    only = set(argv) or None
    unknown = (only or set()) - {name for name, _ in STAGES}
    if unknown:
        print(f"Unknown stage(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        print(f"Available: {', '.join(n for n, _ in STAGES)}", file=sys.stderr)
        return 2

    if not FIXTURES.exists():
        print(f"No {FIXTURES} here — run this from the repository root.",
              file=sys.stderr)
        return 2

    before = after = 0
    # HTML only. The Rentvine fixture is JSON, and every byte of it is data.
    for path in sorted(FIXTURES.rglob("*.html")):
        original = path.read_text(encoding="utf-8", errors="surrogateescape")
        text = strip(original, only)
        if text != original:
            path.write_text(text, encoding="utf-8", errors="surrogateescape")
        before += len(original)
        after += len(text)
        print(f"{len(original) // 1024:6d} KB -> {len(text) // 1024:5d} KB  {path}")

    print(f"\n{before // 1024} KB -> {after // 1024} KB "
          f"({100 * after // max(before, 1)}% of original)")
    print("Now verify: python -m tools.parse_snapshot after.json && "
          "diff before.json after.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
