"""Field extraction for Buildium-hosted rental sites (*.managebuilding.com).

The index lists cards, but they carry no link to their own detail page — every
card shares one ancestor holding all the links, so card and id cannot be paired
reliably. The detail pages carry strictly more (a pet policy, which the index
omits entirely), so this module collects the detail URLs from the index and
parses those instead.

Produces fields directly, so sites using it are registered with
`title_format = "structured"`.
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..dates import parse_available
from ..extract import cats_allowed_from_text, dogs_allowed_from_text
from ..models import UNKNOWN
from ..place import city_of, region_of

#: /Resident/public/rentals/<numeric id> — the bare /rentals index and the
#: rental-application link must not be mistaken for listings.
LISTING_HREF_RE = re.compile(r"/Resident/public/rentals/\d+/?$")

PRICE_RE = re.compile(r"\$\s*([\d,]+)")
BED_RE = re.compile(r"([\d.]+)\s*Bed", re.IGNORECASE)
BATH_RE = re.compile(r"([\d.]+)\s*Bath", re.IGNORECASE)
SQFT_RE = re.compile(r"([\d,]+)\s*sqft", re.IGNORECASE)
PET_RE = re.compile(r"\b(pets?|cats?|dogs?)\b", re.IGNORECASE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _clean(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ")).strip() if node else ""


def _int(match):
    return int(match.group(1).replace(",", "")) if match else UNKNOWN


def find_listing_urls(index_html: str, base_url: str) -> list[str]:
    """Absolute detail URLs for every rental on the index."""
    soup = BeautifulSoup(index_html, "html.parser")
    urls = []
    for anchor in soup.select("a[href*='/Resident/public/rentals/']"):
        url = urljoin(base_url, anchor["href"])
        if LISTING_HREF_RE.search(url) and url not in urls:
            urls.append(url)
    return urls


def _address(soup) -> str:
    """Full address. The h1 holds the street and the city/state/zip lines."""
    heading = soup.select_one("h1")
    if heading is None:
        return UNKNOWN
    lines = [line.strip() for line in heading.get_text("\n").splitlines() if line.strip()]
    return ", ".join(lines) if lines else UNKNOWN


def _summary(description: str) -> str:
    """Opening sentence of the description, used as a headline.

    Buildium publishes no headline of its own — its only title is the street
    address, which is already its own column. The first sentence reads like the
    marketing headline every other source provides.
    """
    if not description or description == UNKNOWN:
        return UNKNOWN
    return SENTENCE_SPLIT_RE.split(description)[0].strip() or UNKNOWN


def _description(soup) -> str:
    """Join every description block.

    Pages carry more than one `.unit-detail__description`: a short property-type
    blurb and the real body copy. Taking only the first lost up to 97% of the
    text on some listings.
    """
    parts = [_clean(node) for node in soup.select(".unit-detail__description")]
    joined = " ".join(part for part in parts if part).strip()
    return joined or UNKNOWN


def _pets(description: str) -> str:
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(description or "")
                 if PET_RE.search(s)]
    return " ".join(sentences) if sentences else UNKNOWN


def parse_detail_fields(detail_html: str) -> dict:
    """Turn one Buildium rental page into a field dict."""
    soup = BeautifulSoup(detail_html, "html.parser")

    address = _address(soup)
    info = " ".join(_clean(el) for el in soup.select(".unit-detail__unit-info-item"))
    price_text = _clean(soup.select_one(".unit-detail__price"))
    description = _description(soup)
    available, available_now = parse_available(
        _clean(soup.select_one(".unit-detail__available-date")))

    bath = BATH_RE.search(info)
    region = region_of(city_of(address), address)

    pets_raw = _pets("" if description == UNKNOWN else description)

    return {
        "link": UNKNOWN,  # filled in by the caller, which knows the URL
        "address": address,
        "region": region,
        "price": _int(PRICE_RE.search(price_text)),
        "bedrooms": _int(BED_RE.search(info)),
        "bathrooms": bath.group(1) if bath else UNKNOWN,
        "sqft": _int(SQFT_RE.search(info)),
        "available": available,
        "available_now": available_now,
        "cats_allowed": cats_allowed_from_text(pets_raw),
        "dogs_allowed": dogs_allowed_from_text(pets_raw),
        "property_type": UNKNOWN,
        "summary": _summary(description),
        "pets_raw": pets_raw,
    }
