"""Structural checks on the page's inline script.

There is no JavaScript engine in the test environment, so these cannot prove
the script *works*. They do catch the failures that a template of this size
actually produces: an unbalanced brace, a reference to an element that is not
in the markup, and a payload key the script reads but Python never sends.

The balance check strips string literals before counting, so a `'http://'` in
the source is not mistaken for the start of a comment. It looks only at the
inline script, never at the surrounding HTML and CSS, which is what made an
earlier attempt at this false-fail.
"""

import re

import pytest

from bendrentals.mapdata import records_from_rows
from bendrentals.models import Listing
from bendrentals.pagehtml import render

BACKSLASH = chr(92)


@pytest.fixture(scope="module")
def page():
    row = dict.fromkeys(Listing.fieldnames(), "?")
    row.update(
        company="A Co", link="https://x/1", address="1 A St, Bend, OR 97701",
        region="SW Bend", price="2495", bedrooms="0", bathrooms="1",
        sqft="600", cats_allowed="True", dogs_allowed="?",
        maps_link="https://m/1", summary="Studio", lat="44.05", lon="-121.31",
    )
    mapped, unmapped = records_from_rows([row])
    return render(mapped, unmapped)


@pytest.fixture(scope="module")
def script(page):
    blocks = re.findall(r"<script>\n(.*?)</script>", page, re.S)
    assert len(blocks) == 1, f"expected one inline script, found {len(blocks)}"
    return blocks[0]


def without_strings(text):
    """Drop string literals and line comments, so brackets can be counted."""
    out, i, n = [], 0, len(text)
    while i < n:
        char = text[i]
        if char in "'\"":
            quote = char
            i += 1
            while i < n and text[i] != quote:
                i += 2 if text[i] == BACKSLASH else 1
            i += 1
            continue
        if text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                break
            continue
        out.append(char)
        i += 1
    return "".join(out)


@pytest.mark.parametrize("opener,closer", [("{", "}"), ("(", ")"), ("[", "]")])
def test_brackets_balance(script, opener, closer):
    bare = without_strings(script)
    assert bare.count(opener) == bare.count(closer)


def test_string_literals_are_not_mistaken_for_comments():
    """The guard on the guard: '//' inside a URL must not eat the rest."""
    assert without_strings("var a = 'http://x'; var b = 1;") == "var a = ; var b = 1;"


def test_every_element_the_script_looks_for_is_in_the_page(page, script):
    names = set(re.findall(r"getElementById\('([^']+)'\)", script))
    assert names, "found no getElementById calls — has the script changed shape?"
    for name in sorted(names):
        assert f'id="{name}"' in page, f"script looks for #{name}, page has none"


def test_every_payload_key_the_script_reads_is_sent(page, script):
    block = re.search(r'id="payload"[^>]*>(.*?)</script>', page, re.S).group(1)
    sent = set(re.findall(r'"(\w+)":', block))
    used = set(re.findall(r"\bD\.(\w+)", script))
    assert used, "found no payload reads — has the script changed shape?"
    assert not (used - sent), f"script reads keys Python never sends: {used - sent}"


def test_listing_values_are_only_ever_written_as_text(script):
    """innerHTML on a scraped value is how a summary becomes markup."""
    assert "innerHTML" not in script
    assert "outerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "document.write" not in script


def test_external_links_are_opened_safely(script):
    assert "rel = 'noopener noreferrer'" in script


def test_the_unmappable_links_are_divided(script):
    """"view | map" — the divider sits outside both anchors."""
    assert "sep.textContent = '|'" in script
    assert "sep.className = 'sep'" in script


def test_the_divider_is_not_styled_as_a_link(page):
    """It inherits the khaki link colour otherwise, and reads as a third link."""
    assert "#unmapped .sep { color: var(--muted); }" in page
