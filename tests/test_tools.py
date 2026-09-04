"""The fixture tools rewrite test data, so they get tests of their own.

`strip_fixtures` is only safe because `parse_snapshot` can prove a strip
changed nothing. These pin the parts of that pair that could quietly go wrong:
a regex that eats content, and a snapshot that covers less than it claims to.
"""

import json
import shutil

from tools.parse_snapshot import FIXTURES, snapshot
from tools.strip_fixtures import STAGES, main, strip

STAGE_NAMES = [name for name, _ in STAGES]


# --- stripping ---------------------------------------------------------------

def test_a_script_block_goes_and_its_surroundings_stay():
    html = "<p>keep</p><script>var x = 1;</script><p>also keep</p>"
    assert strip(html) == "<p>keep</p><p>also keep</p>"


def test_a_style_block_goes():
    assert strip("<a>x</a><style>.a{color:red}</style>") == "<a>x</a>"


def test_a_base64_payload_is_truncated_but_stays_a_data_uri():
    """squarespace reads the first image's src for a filename.

    It has to keep looking like a data: URI, or the bathroom fallback would
    start reading "STRIPPED" as a photo name.
    """
    html = '<img src="data:image/png;base64,' + "A" * 400 + '">'
    stripped = strip(html)
    assert "data:image/png;base64,STRIPPED" in stripped
    assert "AAAA" not in stripped


def test_a_short_data_uri_is_left_alone():
    # Below the threshold: not worth the risk of touching a real value.
    html = '<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">'
    assert strip(html) == html


def test_a_real_image_filename_survives():
    html = '<img data-src="https://cdn.example/photo-3-br-25-bath.jpg">'
    assert strip(html) == html


def test_srcset_goes_and_src_stays():
    html = '<img src="a.jpg" srcset="a-100.jpg 100w, a-200.jpg 200w" alt="x">'
    assert strip(html) == '<img src="a.jpg" alt="x">'


def test_padding_collapses_but_ordinary_spacing_does_not():
    assert strip("a" + " " * 400 + "b") == "a b"
    assert strip("<p>two  words</p>") == "<p>two  words</p>"


def test_text_content_is_never_removed():
    html = "<h1>Sagewood House SW Bend</h1><p>$3,695.00 Per Month | 3 Beds</p>"
    assert strip(html) == html


def test_one_stage_can_be_run_alone():
    html = "<script>x</script><style>y</style>"
    assert strip(html, {"scripts"}) == "<style>y</style>"


def test_an_unknown_stage_name_is_refused_by_name(capsys):
    assert main(["nonsense"]) == 2
    err = capsys.readouterr().err
    assert "nonsense" in err
    assert "padding" in err          # names the real ones


def test_stripping_is_idempotent():
    html = '<p>x</p><script>a</script>' + "  " * 30 + '<img srcset="a 1w">'
    once = strip(html)
    assert strip(once) == once


# --- the snapshot that makes it safe -----------------------------------------

def test_the_snapshot_covers_every_fixture_directory():
    """A source missing from here could be broken by a strip unnoticed."""
    captured = snapshot()
    directories = {p.name for p in FIXTURES.iterdir() if p.is_dir()}
    for name in directories:
        assert any(key.startswith(f"{name}/") for key in captured), name


def test_the_snapshot_captures_the_photo_filename():
    """The least reliable value in the project, and the easiest to break."""
    captured = snapshot()
    assert any("image_filename" in json.dumps(value)
               for key, value in captured.items()
               if key.startswith("trailhead/detail"))


def test_the_snapshot_is_stable_between_runs():
    once = json.dumps(snapshot(), sort_keys=True, ensure_ascii=False)
    twice = json.dumps(snapshot(), sort_keys=True, ensure_ascii=False)
    assert once == twice


def test_stripping_changes_nothing_the_parsers_read(tmp_path):
    """The whole premise: a strip is invisible to every parser.

    Runs against a copy, never the real fixtures — a test that rewrites its
    own inputs is how a fixture quietly rots. Re-capture an unstripped page
    and this is what says the strip is still safe for it.

    All stages at once rather than one test each: parsing the fixture set is
    the expensive part, and six runs of it made the suite five times slower
    for a distinction only useful while bisecting a failure. When it does
    fail, `python -m tools.strip_fixtures <stage>` narrows it down.
    """
    copy = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, copy)
    before = snapshot(copy)

    for path in sorted(copy.rglob("*.html")):
        original = path.read_text(encoding="utf-8", errors="surrogateescape")
        path.write_text(strip(original), encoding="utf-8",
                        errors="surrogateescape")

    assert snapshot(copy) == before


def test_every_stage_is_reachable_by_name():
    """`strip_fixtures <stage>` is the bisect path when the test above fails."""
    assert STAGE_NAMES == ["scripts", "styles", "base64", "srcset",
                           "padding", "blanks"]
