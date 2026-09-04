"""Reads sites.toml: the scrape settings, and each site's parser bindings."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

REQUIRED = ("label", "company", "index_url", "structure", "title_format")
OPTIONAL = {"status": "candidate", "notes": ""}

#: Sites with a working parser. Only these run on a bare `scrape.py`.
READY = "ready"

#: Every source writes into one file. The company column says which is which.
DATA_DIR = Path("data")
LISTINGS_CSV = DATA_DIR / "listings.csv"
SNAPSHOT_DIR = DATA_DIR / "snapshots"


@dataclass(frozen=True)
class Settings:
    """The `[scrape]` table in sites.toml."""

    #: Keep only listings whose address names this city. Empty means every
    #: city a source publishes. See filters.py for why this is not symmetric.
    city: str = ""


@dataclass(frozen=True)
class Site:
    key: str
    label: str
    #: Written into every row's `company` column.
    company: str
    index_url: str
    structure: str
    title_format: str
    #: "ready" once a parser exists; "candidate" while structure/title_format
    #: are still a plan rather than working code.
    status: str = "candidate"
    notes: str = ""

    @property
    def is_ready(self) -> bool:
        return self.status == READY


def load_registry(path: Path | str = "sites.toml") -> tuple[Settings, dict[str, Site]]:
    """Settings and every configured site, keyed by its registry key."""
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)

    settings = Settings(**{
        name: raw.get("scrape", {}).get(name, default)
        for name, default in (("city", Settings.city),)
    })

    sites = {}
    for key, entry in raw.get("sites", {}).items():
        missing = [field for field in REQUIRED if field not in entry]
        if missing:
            raise ValueError(
                f"Site '{key}' in {path} is missing required keys: {', '.join(missing)}"
            )
        values = {field: entry[field] for field in REQUIRED}
        values.update({k: entry.get(k, default) for k, default in OPTIONAL.items()})
        sites[key] = Site(key=key, **values)
    return settings, sites


def load_sites(path: Path | str = "sites.toml") -> dict[str, Site]:
    """Just the sites, for callers with no interest in the settings."""
    return load_registry(path)[1]


def ready_sites(sites: dict[str, Site]) -> dict[str, Site]:
    """Only the sites with a working parser."""
    return {key: site for key, site in sites.items() if site.is_ready}


def display_names(sites: dict[str, Site]) -> dict[str, str]:
    """Full company name -> the short `label` the page shows.

    The CSV stores the full name, because that is the useful thing in a data
    file. The page shows the label, because a column reading "... Property
    Management" thirteen times is noise.

    Editing a label in sites.toml and re-running build_page.py is enough to
    change the page: nothing in the CSV moves, so no re-scrape is needed. A
    company with no registry entry keeps its full name rather than vanishing.
    """
    return {site.company: site.label for site in sites.values()}
