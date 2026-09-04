"""Wires structure + format + extraction into Listing rows."""

import importlib
import sys
from datetime import datetime

from .extract import (
    cats_allowed_from_text, dogs_allowed_from_text, extract_bathrooms, extract_pets,
)
from .fetch import resolve as resolve_url
from .geocode import parse_google_maps_place
from .models import UNKNOWN, Listing, google_maps_link
from .registry import Site

#: Fields a `parse_index` structure is expected to produce for each listing.
STRUCTURED_FIELDS = (
    "link", "address", "region", "price", "bedrooms", "bathrooms", "sqft",
    "property_type", "available", "available_now", "cats_allowed",
    "dogs_allowed", "summary", "pets_raw",
)


class ScrapeError(RuntimeError):
    """Raised when a scrape produced no listings — almost always changed markup."""


def _load(package: str, name: str):
    return importlib.import_module(f".{package}.{name}", package="bendrentals")


def build_listing(
    link: str, detail_html: str, structure: str, title_format: str, scraped_at: str
) -> Listing:
    """Turn one detail page into a Listing. Never raises on unparseable text.

    The page's body copy is read here for bathrooms and the pet policy, then
    discarded: `summary` is the only prose the CSV keeps.
    """
    structure_module = _load("structures", structure)
    formatter = _load("formats", title_format)

    detail = structure_module.parse_detail(detail_html)
    parsed = formatter.parse_title(detail["title"])
    status = "ok"

    if parsed is None:
        # Keep the row. Preserve the raw title so nothing is lost.
        status = "partial"
        print(f"WARNING: unparseable title at {link}: {detail['title']!r}", file=sys.stderr)
        parsed = {
            "price": UNKNOWN, "bedrooms": UNKNOWN, "sqft": UNKNOWN,
            "summary": detail["title"], "region": UNKNOWN,
        }

    if detail["address"] == UNKNOWN or detail["description"] == UNKNOWN:
        status = "partial"

    description = "" if detail["description"] == UNKNOWN else detail["description"]
    bathrooms, _ = extract_bathrooms(description, detail["image_filename"])
    pets_raw = extract_pets(description)

    return Listing(
        company=UNKNOWN,  # set by scrape_site, which knows the registry entry
        link=link,
        price=parsed["price"],
        bedrooms=parsed["bedrooms"],
        bathrooms=bathrooms,
        sqft=parsed["sqft"],
        # This source states no property type and no availability field.
        property_type=UNKNOWN,
        available=UNKNOWN,
        available_now=UNKNOWN,
        region=parsed["region"],
        address=detail["address"],
        cats_allowed=cats_allowed_from_text(pets_raw),
        dogs_allowed=dogs_allowed_from_text(pets_raw),
        maps_link=google_maps_link(detail["address"]),
        lat=UNKNOWN,
        lon=UNKNOWN,
        summary=parsed["summary"],
        pets_raw=pets_raw,
        scraped_at=scraped_at,
        parse_status=status,
    )


def _address_from_map_link(fields: dict, map_link, resolver) -> None:
    """Fill address/lat/lon from a site's own "view on a map" short link.

    Some sites publish no street address but do link their listing to a map.
    Following that redirect yields a URL containing both the address and its
    coordinates -- no page content is read, and no geocoding request is needed.
    """
    if not map_link or map_link == UNKNOWN or resolver is None:
        return
    try:
        place = parse_google_maps_place(resolver(map_link))
    except Exception as error:
        print(f"WARNING: could not resolve map link {map_link}: {error}", file=sys.stderr)
        return
    if not place:
        return
    address, lat, lon = place
    fields["address"] = address
    fields.setdefault("lat", lat)
    fields.setdefault("lon", lon)


def listing_from_fields(fields: dict, scraped_at: str, omitted=frozenset()) -> Listing:
    """Build a Listing from a structure that produced fields directly.

    Used by platforms like AppFolio that expose each value in its own element,
    so there is no title string to decode. Registered as
    `title_format = "structured"`.

    `omitted` names fields the *site* never publishes. Those stay "?" without
    marking the row partial — "partial" means we failed to read something that
    was there, not that the source declined to say it.
    """
    missing = [name for name in STRUCTURED_FIELDS if name not in fields]
    if missing:
        raise ScrapeError(f"structure omitted required fields: {', '.join(missing)}")

    expected = [n for n in ("price", "bedrooms", "address") if n not in omitted]
    incomplete = any(fields[name] == UNKNOWN for name in expected)

    return Listing(
        company=UNKNOWN,  # set by scrape_site, which knows the registry entry
        link=fields["link"],
        address=fields["address"],
        region=fields["region"],
        price=fields["price"],
        bedrooms=fields["bedrooms"],
        bathrooms=fields["bathrooms"],
        sqft=fields["sqft"],
        property_type=fields["property_type"],
        available=fields["available"],
        available_now=fields["available_now"],
        cats_allowed=fields["cats_allowed"],
        dogs_allowed=fields["dogs_allowed"],
        maps_link=google_maps_link(fields["address"]),
        # A structure may supply coordinates (Rentvine does); otherwise the
        # geocoding step fills these in from the address.
        lat=fields.get("lat", UNKNOWN),
        lon=fields.get("lon", UNKNOWN),
        summary=fields["summary"],
        pets_raw=fields["pets_raw"],
        scraped_at=scraped_at,
        parse_status="partial" if incomplete else "ok",
    )


def scrape_site(site: Site, fetcher, *, now: datetime | None = None,
                resolver=resolve_url) -> list[Listing]:
    """Fetch a site's listings, tagged with the company that manages them.

    Raises ScrapeError if none are found.
    """
    listings = _scrape(site, fetcher, now=now, resolver=resolver)
    # Every source shares one CSV, so each row has to say where it came from.
    for listing in listings:
        listing.company = site.company
    return listings


def _scrape(site: Site, fetcher, *, now=None, resolver=resolve_url) -> list[Listing]:
    """Three shapes of structure module are supported:

    - `parse_index` — every field is on the index page (AppFolio). One request.
    - `find_listing_urls` + `parse_detail_fields` — labelled fields on a detail
      page per listing (Preferred Residential).
    - `find_listing_urls` + `parse_detail` — a title string plus a detail page
      per listing (Squarespace), decoded by the site's `title_format`.
    """
    structure = _load("structures", site.structure)
    scraped_at = (now or datetime.now()).isoformat(timespec="seconds")

    index_html = fetcher(site.index_url)

    omitted = getattr(structure, "OMITTED_FIELDS", frozenset())

    if hasattr(structure, "parse_index"):
        rows = structure.parse_index(index_html, site.index_url)
        if not rows:
            raise ScrapeError(
                f"No listings found on {site.index_url} — the page markup has probably changed."
            )
        return [listing_from_fields(row, scraped_at, omitted) for row in rows]

    if not hasattr(structure, "find_listing_urls"):
        raise ScrapeError(
            f"structure '{site.structure}' exposes none of parse_index, "
            "find_listing_urls -- it cannot be used to scrape a site."
        )

    links = structure.find_listing_urls(index_html, site.index_url)
    if not links:
        raise ScrapeError(
            f"No listings found on {site.index_url} — the page markup has probably changed."
        )

    if hasattr(structure, "parse_detail_fields"):
        map_field = getattr(structure, "MAP_LINK_FIELD", None)
        listings = []
        for link in links:
            fields = structure.parse_detail_fields(fetcher(link))
            fields["link"] = link  # only the caller knows which URL this was
            if map_field and fields.get("address") == UNKNOWN:
                _address_from_map_link(fields, fields.get(map_field), resolver)
            listings.append(listing_from_fields(fields, scraped_at, omitted))
        return listings

    return [
        build_listing(link, fetcher(link), site.structure, site.title_format, scraped_at)
        for link in links
    ]
