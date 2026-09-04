"""Pull loosely-structured fields out of free-text listing descriptions.

Bathrooms and pet policy are not structured fields on the title-format sources.
Both are best-effort. Structured sources (AppFolio, Buildium, Rentvine,
prbend) read these from real markup and do not use this module for bathrooms.
"""

import re

from .models import UNKNOWN

# "2.5 baths", "1 bath", "2 bathrooms" — requires a number immediately before,
# so prose like "tiled bathroom vanities" does not match.
BATH_TEXT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:full\s+|half\s+)?bath", re.IGNORECASE)

# Photo filenames sometimes encode "3-br-25-bath-house...", decimal point stripped.
BATH_FILE_RE = re.compile(r"(\d+)-bath", re.IGNORECASE)

PET_RE = re.compile(r"\b(?:pets?|cats?|dogs?)\b", re.IGNORECASE)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _normalise(value: str) -> str:
    """'2.0' -> '2', '2.5' -> '2.5', '1' -> '1'."""
    number = float(value)
    return str(int(number)) if number == int(number) else str(number)


def _from_filename(digits: str) -> str:
    """Filenames drop the decimal point: '25' -> 2.5, '2' -> 2.

    A bare integer of 2+ digits is read as a decimal, because a listing with 25
    bathrooms is implausible while 2.5 is common. Single digits are literal.
    This is the least reliable input in the system, which is why it ranks below
    prose, and its value is the least trustworthy in the row.
    """
    if len(digits) >= 2:
        return _normalise(f"{digits[:-1]}.{digits[-1]}")
    return _normalise(digits)


def extract_bathrooms(description: str, image_filename: str) -> tuple[str, str]:
    """Return (value, source). Source is description | image_filename | not_found."""
    match = BATH_TEXT_RE.search(description or "")
    if match:
        return _normalise(match.group(1)), "description"

    match = BATH_FILE_RE.search(image_filename or "")
    if match:
        return _from_filename(match.group(1)), "image_filename"

    return UNKNOWN, "not_found"


def extract_pets(description: str) -> str:
    """Return the first sentence mentioning pets, verbatim and uninterpreted."""
    for sentence in SENTENCE_SPLIT_RE.split(description or ""):
        if PET_RE.search(sentence):
            return sentence.strip()
    return UNKNOWN


#: A ban on pets in general excludes every animal, in either phrasing.
BLANKET_NO_RE = re.compile(
    r"no\s+pets?\b"
    r"|pets?\s+(?:will\s+|are\s+)?not\s+(?:be\s+)?"
    r"(?:considered|allowed|permitted|accepted)",
    re.IGNORECASE,
)

#: Blanket permission, which does say something about every animal. Deliberately
#: narrower than its refusal counterpart: "pets considered" is not permission,
#: so it is absent here while "cats considered" is matched below.
BLANKET_YES_RE = re.compile(
    r"pets?\s+(?:are\s+)?(?:allowed|welcome|ok\b)|pet[- ]friendly",
    re.IGNORECASE,
)


#: The hedging a listing puts between the animal and the verdict:
#: "dogs are allowed", "dogs will be considered", "dogs may be considered".
_HEDGE = r"(?:will\s+|may\s+|are\s+)?(?:be\s+)?"

#: Verdict words. "Considered" counts as permission only where the animal is
#: named — BLANKET_YES_RE deliberately omits it.
_VERDICT = r"(?:allowed|considered|permitted|accepted|welcome)"


def _no_pattern(plural: str, singular: str) -> re.Pattern:
    return re.compile(
        rf"{plural}\s+{_HEDGE}not\s+(?:be\s+)?{_VERDICT}"
        rf"|no\s+{plural}\b|{plural}\s*:\s*no\b",
        re.IGNORECASE,
    )


def _yes_pattern(plural: str, singular: str) -> re.Pattern:
    # "not" is never one of the hedge words, so this cannot match a refusal --
    # and refusals are tested first regardless.
    return re.compile(
        rf"{plural}\s+{_HEDGE}{_VERDICT}|{plural}\s+ok\b|{singular}[- ]friendly",
        re.IGNORECASE,
    )


#: Per-animal wording. Order matters wherever these are used: refusal is
#: checked before permission, so "cats not allowed" is never read as "allowed".
ANIMALS = {
    "cats": (_no_pattern(r"cats?", "cat"), _yes_pattern(r"cats?", "cat")),
    "dogs": (_no_pattern(r"dogs?", "dog"), _yes_pattern(r"dogs?", "dog")),
}


def _allowed(text: str, animal: str) -> str:
    """"True" / "False" / "?" for one animal, from a pet-policy string.

    Silence is never refusal. A policy mentioning only dogs leaves cats
    unknown, because guessing "False" would hide listings that do take cats.
    The animal's own wording wins over a blanket statement, so
    "Pets allowed, no cats" reads as dogs yes, cats no.
    """
    if not text or text == UNKNOWN:
        return UNKNOWN
    refuses, permits = ANIMALS[animal]
    if refuses.search(text):
        return "False"
    if permits.search(text):
        return "True"
    if BLANKET_NO_RE.search(text):
        return "False"
    if BLANKET_YES_RE.search(text):
        return "True"
    return UNKNOWN


def cats_allowed_from_text(text: str) -> str:
    """"True" / "False" / "?" for cats. See `_allowed`."""
    return _allowed(text, "cats")


def dogs_allowed_from_text(text: str) -> str:
    """"True" / "False" / "?" for dogs. See `_allowed`."""
    return _allowed(text, "dogs")
