from unittest.mock import MagicMock

import pytest
import requests

from bendrentals.fetch import REQUEST_DELAY, USER_AGENT, FetchError, get


class FakeResponse:
    def __init__(self, text="<html>ok</html>"):
        self.text = text

    def raise_for_status(self):
        return None


def test_user_agent_is_vague_and_carries_no_identity():
    assert USER_AGENT == "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    lowered = USER_AGENT.lower()
    for leak in ("scraper", "bot", "python", "apt", "@"):
        assert leak not in lowered


def test_default_delay_is_polite():
    assert REQUEST_DELAY == 1.5


def test_returns_response_text():
    session = MagicMock()
    session.get.return_value = FakeResponse("<html>hi</html>")
    assert get("https://example.com", session=session, delay=0) == "<html>hi</html>"


def test_sends_the_user_agent_header():
    session = MagicMock()
    session.get.return_value = FakeResponse()
    get("https://example.com", session=session, delay=0)
    headers = session.get.call_args.kwargs["headers"]
    assert headers["User-Agent"] == USER_AGENT


def test_retries_then_succeeds():
    session = MagicMock()
    session.get.side_effect = [
        requests.RequestException("boom"),
        FakeResponse("<html>second try</html>"),
    ]
    assert get("https://example.com", session=session, delay=0) == "<html>second try</html>"
    assert session.get.call_count == 2


def test_raises_fetch_error_after_exhausting_retries():
    session = MagicMock()
    session.get.side_effect = requests.RequestException("boom")
    with pytest.raises(FetchError) as excinfo:
        get("https://example.com", session=session, retries=2, delay=0)
    assert "https://example.com" in str(excinfo.value)
    assert session.get.call_count == 3  # initial attempt plus two retries


def test_refuses_disallowed_format_json_urls():
    # The rule is per-domain: this is a Squarespace-hosted source, whose
    # robots.txt disallows it. See test_fetch_domains for the scoping tests.
    session = MagicMock()
    with pytest.raises(ValueError, match="robots.txt"):
        get("https://www.trailheadpropertymanagement.com/page?format=json",
            session=session, delay=0)
    session.get.assert_not_called()


def test_connect_and_read_timeouts_are_separate():
    """A host that never completes a handshake is not a slow page.

    prbend.com answers in under a second from a home connection and never
    answers at all from GitHub's runners. A single long timeout made that
    source cost ~95s of every scheduled run.
    """
    from bendrentals.fetch import TIMEOUT
    connect, read = TIMEOUT
    assert connect < read
    assert connect <= 15


def test_the_timeout_is_passed_through_to_requests():
    from unittest.mock import MagicMock

    from bendrentals.fetch import TIMEOUT, get

    session = MagicMock()
    session.get.return_value = FakeResponse()
    get("https://example.com/x", session=session, delay=0)
    assert session.get.call_args.kwargs["timeout"] == TIMEOUT
