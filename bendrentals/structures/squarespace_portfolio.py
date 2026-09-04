"""Text extraction for Squarespace portfolio pages.

Index pages list listings as <a class="grid-item">. Detail pages render as a
short stack of text lines inside <main>: title, address, then description
paragraphs, followed by navigation chrome we discard.

This module knows nothing about title conventions — see bendrentals.formats.
"""

import re
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup

from ..models import UNKNOWN

#: Trailing UI text that is not part of the listing.
NAV_TEXT = {"Next", "Previous", "Request an Application"}

#: Addresses on Bend sources always end with ", Bend OR <zip>".
ADDRESS_RE = re.compile(r",\s*Bend\s+OR\s+\d{5}", re.IGNORECASE)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def find_listing_urls(index_html: str, base_url: str) -> list[str]:
    """Absolute URLs for each listing on an index page, in source order."""
    urls = []
    for anchor in _soup(index_html).select("a.grid-item[href]"):
        url = urljoin(base_url, anchor["href"])
        if url not in urls:
            urls.append(url)
    return urls


def _content_lines(html: str) -> list[str]:
    """Visible text lines inside <main>, stopping at navigation chrome."""
    main = _soup(html).select_one("main")
    if main is None:
        return []
    for tag in main(["script", "style"]):
        tag.decompose()

    lines = []
    for raw in main.get_text("\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line in NAV_TEXT:
            break
        lines.append(line)
    return lines


def _first_image_filename(html: str) -> str:
    """Filename of the first listing photo, URL-decoded."""
    main = _soup(html).select_one("main")
    if main is None:
        return UNKNOWN
    for img in main.select("img"):
        src = img.get("data-src") or img.get("src")
        if src:
            return unquote(src.rsplit("/", 1)[-1])
    return UNKNOWN


def parse_detail(detail_html: str) -> dict:
    """Split a detail page into title, address, description and photo filename."""
    lines = _content_lines(detail_html)
    if not lines:
        return {
            "title": UNKNOWN, "address": UNKNOWN,
            "description": UNKNOWN, "image_filename": UNKNOWN,
        }

    title = lines[0]
    address = UNKNOWN
    address_index = None
    for index, line in enumerate(lines[1:], start=1):
        if ADDRESS_RE.search(line):
            address, address_index = line, index
            break

    body_start = (address_index + 1) if address_index is not None else 1
    body = " ".join(lines[body_start:]).strip()

    return {
        "title": title,
        "address": address,
        "description": body or UNKNOWN,
        "image_filename": _first_image_filename(detail_html),
    }
