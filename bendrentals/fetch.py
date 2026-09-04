"""HTTP fetching: deliberately slow, deliberately anonymous.

Politeness is per-domain. A host that publishes a crawl delay gets it; a host
whose usage policy requires identification gets a User-Agent that identifies the
application and nothing else.
"""

import time
from urllib.parse import parse_qs, urlparse

import requests

#: Vague on purpose. No product name, no contact address, no user identity.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

#: Seconds to wait before each request, unless a domain overrides it.
REQUEST_DELAY = 1.5

#: Per-domain delays, keyed by registrable domain. Subdomains inherit.
#:  - appfolio.com publishes `Crawl-delay: 10` in robots.txt.
#:  - openstreetmap.org caps Nominatim at 1 request/second. 10s is well under
#:    that; bounded backfills may pass a smaller delay explicitly.
DOMAIN_DELAYS = {
    "appfolio.com": 10.0,
    "openstreetmap.org": 10.0,
    # A US government bulk-geocoding service; no published crawl delay.
    "census.gov": 1.0,
}

#: Delay for a bounded one-off geocoding backfill. Still 0.5 req/s, half the cap.
BACKFILL_DELAY = 2.0

#: OSM's usage policy requires a User-Agent identifying the application and a
#: way to make contact. The repository URL is that route: it has an issue
#: tracker. No email address appears here, or anywhere else in this project.
NOMINATIM_USER_AGENT = "Bend-Rentals/0.1 (+https://github.com/NBPub/bend_rentals)"

DOMAIN_USER_AGENTS = {
    "openstreetmap.org": NOMINATIM_USER_AGENT,
    # Identifying the caller to a public API is good practice, and this
    # string carries no personal information.
    "census.gov": NOMINATIM_USER_AGENT,
}

TIMEOUT = 30

#: `format` values Squarespace's robots.txt disallows.
SQUARESPACE_DISALLOWED_FORMATS = frozenset(
    {"json", "json-pretty", "page-context", "main-content", "ical"}
)

#: robots.txt is per-domain, and so is this rule. It applied globally twice
#: before and broke legitimate APIs both times — Nominatim's `format=jsonv2`
#: and the Census geocoder's `format=json`. Add a domain here when adding a
#: Squarespace-hosted source; do not make this a blanket rule again.
DOMAIN_DISALLOWED_FORMATS = {
    "trailheadpropertymanagement.com": SQUARESPACE_DISALLOWED_FORMATS,
    "epmbend.com": SQUARESPACE_DISALLOWED_FORMATS,
}


class FetchError(RuntimeError):
    """Raised when a URL could not be retrieved after all retries."""


def _has_disallowed_format(url: str) -> bool:
    disallowed = DOMAIN_DISALLOWED_FORMATS.get(_domain(url))
    if not disallowed:
        return False
    values = parse_qs(urlparse(url).query).get("format", [])
    return any(value in disallowed for value in values)


def _domain(url: str) -> str:
    """Registrable-ish domain: the last two labels of the host."""
    host = (urlparse(url).hostname or "").lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def delay_for(url: str) -> float:
    """Seconds to wait before requesting this URL."""
    return DOMAIN_DELAYS.get(_domain(url), REQUEST_DELAY)


def user_agent_for(url: str) -> str:
    """User-Agent for this URL. Vague unless the host's policy requires more."""
    return DOMAIN_USER_AGENTS.get(_domain(url), USER_AGENT)


def resolve(url, *, session=None, delay: float | None = None) -> str:
    """Final URL after following redirects, without reading the page body.

    Used for short links a site publishes about its own listings. This reads a
    Location header, not page content.
    """
    if delay is None:
        delay = delay_for(url)
    session = session or requests.Session()
    if delay:
        time.sleep(delay)
    response = session.get(
        url, headers={"User-Agent": user_agent_for(url)},
        timeout=TIMEOUT, allow_redirects=True,
    )
    return response.url


def get(url, *, session=None, retries: int = 2, delay: float | None = None) -> str:
    """Fetch a URL politely, retrying with exponential backoff.

    `delay` defaults to the domain's configured delay. Pass 0 in tests.

    Raises FetchError if every attempt fails, so callers can exit non-zero
    rather than silently writing a short CSV.
    """
    if _has_disallowed_format(url):
        raise ValueError(f"robots.txt disallows this format parameter: {url}")

    if delay is None:
        delay = delay_for(url)

    session = session or requests.Session()
    headers = {"User-Agent": user_agent_for(url)}
    last_error = None

    for attempt in range(retries + 1):
        if delay:
            time.sleep(delay)
        try:
            response = session.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as error:
            last_error = error
            if attempt < retries and delay:
                time.sleep(delay * (2 ** attempt))

    raise FetchError(f"Failed to fetch {url} after {retries + 1} attempts: {last_error}")
