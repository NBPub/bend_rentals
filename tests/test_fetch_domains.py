import pytest
from unittest.mock import MagicMock

from bendrentals.fetch import USER_AGENT, delay_for, user_agent_for


class FakeResponse:
    def __init__(self, text="<html>ok</html>"):
        self.text = text

    def raise_for_status(self):
        return None


def test_appfolio_gets_its_published_crawl_delay():
    # appfolio.com robots.txt: Crawl-delay: 10
    assert delay_for("https://mountainviewpm.appfolio.com/listings") == 10.0
    assert delay_for("https://bend.appfolio.com/listings?filters[cities][]=Bend") == 10.0


def test_nominatim_gets_its_own_delay():
    assert delay_for("https://nominatim.openstreetmap.org/search?q=x") == 10.0


def test_everything_else_keeps_the_global_delay():
    assert delay_for("https://www.trailheadpropertymanagement.com/portfolio-1") == 1.5
    assert delay_for("https://prbend.com/property/example/") == 1.5


def test_subdomains_match_the_registered_domain():
    # The rule is registered on appfolio.com and must cover every tenant.
    assert delay_for("https://anything.appfolio.com/x") == 10.0


def test_a_lookalike_domain_does_not_match():
    # notappfolio.com must not inherit appfolio.com's rule.
    assert delay_for("https://notappfolio.com/listings") == 1.5


def test_nominatim_identifies_the_application():
    # OSM's usage policy requires a real identifying User-Agent.
    agent = user_agent_for("https://nominatim.openstreetmap.org/search")
    assert "Bend-Rentals" in agent
    assert agent != USER_AGENT


def test_nominatim_user_agent_carries_no_personal_contact():
    agent = user_agent_for("https://nominatim.openstreetmap.org/search")
    assert "@" not in agent


def test_every_other_host_keeps_the_vague_user_agent():
    assert user_agent_for("https://mountainviewpm.appfolio.com/listings") == USER_AGENT
    assert user_agent_for("https://www.trailheadpropertymanagement.com/") == USER_AGENT


def test_get_applies_the_per_domain_user_agent():
    from bendrentals.fetch import get

    session = MagicMock()
    session.get.return_value = FakeResponse()
    get("https://nominatim.openstreetmap.org/search", session=session, delay=0)
    sent = session.get.call_args.kwargs["headers"]["User-Agent"]
    assert "Bend-Rentals" in sent


def test_squarespace_disallowed_formats_are_refused_on_squarespace_hosts():
    from bendrentals.fetch import get

    for bad in ("json", "json-pretty", "page-context", "main-content", "ical"):
        session = MagicMock()
        with pytest.raises(ValueError, match="robots.txt"):
            get(f"https://www.trailheadpropertymanagement.com/x?format={bad}",
                session=session, delay=0)
        session.get.assert_not_called()


def test_the_format_ban_is_per_domain_not_global():
    """robots.txt is per-domain. A global ban broke two legitimate APIs."""
    from bendrentals.fetch import get

    session = MagicMock()
    session.get.return_value = FakeResponse("{}")
    # census.gov legitimately uses format=json and publishes no such rule.
    get("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
        "?address=x&benchmark=Public_AR_Current&format=json",
        session=session, delay=0)
    session.get.assert_called_once()


def test_an_unrelated_host_may_use_format_json():
    from bendrentals.fetch import get

    session = MagicMock()
    session.get.return_value = FakeResponse("{}")
    get("https://example.com/api?format=json", session=session, delay=0)
    session.get.assert_called_once()


def test_jsonv2_is_not_mistaken_for_the_disallowed_json_format():
    """Nominatim uses format=jsonv2, which merely *contains* "format=json"."""
    from bendrentals.fetch import get

    session = MagicMock()
    session.get.return_value = FakeResponse('[{"lat":"44.0","lon":"-121.3"}]')
    body = get(
        "https://nominatim.openstreetmap.org/search?q=x&format=jsonv2&limit=1",
        session=session, delay=0,
    )
    assert "44.0" in body
    session.get.assert_called_once()


def test_format_check_only_looks_at_the_query_parameter():
    # A path that happens to contain the text must not trip the guard.
    from bendrentals.fetch import get

    session = MagicMock()
    session.get.return_value = FakeResponse()
    get("https://www.trailheadpropertymanagement.com/docs/format=json/guide",
        session=session, delay=0)
    session.get.assert_called_once()


def test_resolve_returns_the_final_url_after_redirects():
    """Used for short links a site publishes about its own listings."""
    from bendrentals.fetch import resolve

    final = ("https://www.google.com/maps/place/61473+Linton+Loop,+Bend,+OR+97702"
             "/@44.033057,-121.339462,17z/data=x")
    session = MagicMock()
    session.get.return_value = type("R", (), {"url": final})()
    assert resolve("https://maps.app.goo.gl/abc", session=session, delay=0) == final
    assert session.get.call_args.kwargs["allow_redirects"] is True
