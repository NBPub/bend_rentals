import importlib
from pathlib import Path

import pytest

from bendrentals.registry import (
    LISTINGS_CSV, SNAPSHOT_DIR, load_registry, load_sites, ready_sites,
)

MINIMAL = (
    '[sites.alpha]\n'
    'label = "Alpha"\n'
    'company = "Alpha Property Management"\n'
    'index_url = "https://alpha.example.com/rentals"\n'
    'structure = "squarespace_portfolio"\n'
    'title_format = "craigslist"\n'
)


def test_loads_trailhead_from_the_real_registry():
    trailhead = load_sites("sites.toml")["trailhead"]
    assert trailhead.label == "Trailhead"
    assert trailhead.company == "Trailhead Property Management"
    assert trailhead.index_url == (
        "https://www.trailheadpropertymanagement.com/portfolio-1"
    )
    assert trailhead.structure == "squarespace_portfolio"
    assert trailhead.title_format == "craigslist"


def test_every_site_names_a_distinct_company():
    """The company column is the only thing separating sources in one CSV."""
    companies = [site.company for site in load_sites("sites.toml").values()]
    assert len(companies) == len(set(companies))
    assert all(company.strip() for company in companies)


def test_ready_sites_all_name_a_structure_module_that_exists():
    # Candidates must never run on a bare `scrape.py` — they have no parser.
    ready = ready_sites(load_sites("sites.toml"))
    assert ready, "expected at least one ready site"
    for site in ready.values():
        importlib.import_module(f"bendrentals.structures.{site.structure}")


def test_no_appfolio_url_still_carries_the_personal_bedroom_filter():
    """The public registry filters on use and place, never on a bedroom count."""
    for site in load_sites("sites.toml").values():
        assert "bedrooms" not in site.index_url, site.key


def test_the_appfolio_urls_agree_with_the_configured_city():
    """AppFolio can filter at the source; the other four cannot.

    Both halves have to say the same thing, or the file would hold Bend
    listings from nine companies and everywhere from four.
    """
    settings, sites = load_registry("sites.toml")
    for site in sites.values():
        if site.structure != "appfolio_listings":
            continue
        if settings.city:
            assert f"%5D%5B%5D={settings.city}" in site.index_url, site.key
        else:
            assert "cities" not in site.index_url, site.key


def test_the_shipped_city_is_the_one_the_project_is_named_for():
    assert load_registry("sites.toml")[0].city == "Bend"


def test_city_defaults_to_empty_when_the_scrape_table_is_absent(tmp_path):
    registry = tmp_path / "sites.toml"
    registry.write_text(MINIMAL, encoding="utf-8")
    assert load_registry(registry)[0].city == ""


def test_every_candidate_carries_a_note_explaining_what_is_unresolved():
    # There may be none left; any that exist must say what is unresolved.
    candidates = [s for s in load_sites("sites.toml").values() if not s.is_ready]
    assert all(s.notes.strip() for s in candidates)


def test_status_defaults_to_candidate_when_absent(tmp_path):
    registry = tmp_path / "sites.toml"
    registry.write_text(MINIMAL, encoding="utf-8")
    site = load_sites(registry)["alpha"]
    assert site.status == "candidate"
    assert site.is_ready is False
    assert site.notes == ""


def test_every_source_shares_one_output_file():
    assert LISTINGS_CSV == Path("data") / "listings.csv"
    assert SNAPSHOT_DIR == Path("data") / "snapshots"


def test_loads_multiple_sites(tmp_path):
    registry = tmp_path / "sites.toml"
    registry.write_text(
        MINIMAL
        + '\n[sites.beta]\n'
        'label = "Beta"\n'
        'company = "Beta Rentals"\n'
        'index_url = "https://beta.example.com/vacancies"\n'
        'structure = "squarespace_portfolio"\n'
        'title_format = "craigslist"\n',
        encoding="utf-8",
    )
    sites = load_sites(registry)
    assert sorted(sites) == ["alpha", "beta"]
    assert sites["beta"].company == "Beta Rentals"


def test_missing_required_key_is_reported_clearly(tmp_path):
    registry = tmp_path / "sites.toml"
    registry.write_text('[sites.broken]\nlabel = "Broken"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="broken"):
        load_sites(registry)


def test_a_site_without_a_company_is_rejected(tmp_path):
    registry = tmp_path / "sites.toml"
    registry.write_text(MINIMAL.replace(
        'company = "Alpha Property Management"\n', ""), encoding="utf-8")
    with pytest.raises(ValueError, match="company"):
        load_sites(registry)


def test_every_ready_structure_exposes_a_known_entry_point():
    """Guards the three supported structure shapes.

    A structure with neither parse_index nor find_listing_urls used to fall
    through to the title-format path and fail with a confusing
    ModuleNotFoundError far from the real cause.
    """
    for site in ready_sites(load_sites("sites.toml")).values():
        module = importlib.import_module(f"bendrentals.structures.{site.structure}")
        assert hasattr(module, "parse_index") or hasattr(module, "find_listing_urls"), (
            f"{site.structure} exposes no usable entry point"
        )
        if hasattr(module, "find_listing_urls") and not hasattr(module, "parse_index"):
            assert hasattr(module, "parse_detail_fields") or hasattr(module, "parse_detail")
