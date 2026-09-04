import json

import pytest

from bendrentals.geocode import (
    NOMINATIM_URL,
    GeocodeCache,
    geocode_all,
    normalise_address,
)
from bendrentals.models import UNKNOWN


def test_normalise_collapses_whitespace_case_and_punctuation():
    a = normalise_address("19884 Duck Call Lane,  Bend OR 97702")
    b = normalise_address("19884 duck call lane, Bend  OR  97702")
    assert a == b


def test_normalise_treats_unknown_as_unknown():
    assert normalise_address(UNKNOWN) == ""
    assert normalise_address("") == ""


def test_cache_roundtrips_to_disk(tmp_path):
    path = tmp_path / "geocode.json"
    cache = GeocodeCache(path)
    cache.put("19884 Duck Call Lane, Bend OR 97702", "44.02", "-121.31")
    cache.save()

    reloaded = GeocodeCache(path)
    assert reloaded.get("19884 Duck Call Lane, Bend OR 97702") == ("44.02", "-121.31")


def test_cache_lookup_is_insensitive_to_formatting(tmp_path):
    cache = GeocodeCache(tmp_path / "geocode.json")
    cache.put("19884 Duck Call Lane, Bend OR 97702", "44.02", "-121.31")
    assert cache.get("19884  duck call LANE,  Bend OR 97702") == ("44.02", "-121.31")


def test_cache_miss_returns_none(tmp_path):
    assert GeocodeCache(tmp_path / "geocode.json").get("nowhere") is None


def test_a_failed_lookup_is_remembered_so_it_is_never_retried(tmp_path):
    path = tmp_path / "geocode.json"
    cache = GeocodeCache(path)
    cache.put_failure("Nonexistent Rd, Bend OR 99999")
    cache.save()

    reloaded = GeocodeCache(path)
    assert reloaded.get("Nonexistent Rd, Bend OR 99999") == (UNKNOWN, UNKNOWN)
    assert reloaded.knows("Nonexistent Rd, Bend OR 99999")


def test_geocode_all_never_requests_the_same_address_twice(tmp_path):
    calls = []

    def fake_fetch(url, **kwargs):
        calls.append(url)
        return json.dumps([{"lat": "44.02", "lon": "-121.31"}])

    cache = GeocodeCache(tmp_path / "geocode.json")
    addresses = [
        "19884 Duck Call Lane, Bend OR 97702",
        "19884 Duck Call Lane, Bend OR 97702",   # exact repeat
        "19884  duck call lane,  bend or 97702",  # same place, different text
    ]
    geocode_all(addresses, cache, fetcher=fake_fetch, delay=0)
    assert len(calls) == 1


def test_geocode_all_skips_addresses_already_cached(tmp_path):
    calls = []

    def fake_fetch(url, **kwargs):
        calls.append(url)
        return json.dumps([{"lat": "1", "lon": "2"}])

    cache = GeocodeCache(tmp_path / "geocode.json")
    cache.put("Known St, Bend OR 97701", "44.0", "-121.0")
    geocode_all(["Known St, Bend OR 97701"], cache, fetcher=fake_fetch, delay=0)
    assert calls == []


def test_geocode_all_queries_nominatim_with_the_address(tmp_path):
    seen = []

    def fake_fetch(url, **kwargs):
        seen.append(url)
        return json.dumps([{"lat": "44.02", "lon": "-121.31"}])

    cache = GeocodeCache(tmp_path / "geocode.json")
    geocode_all(["19884 Duck Call Lane, Bend OR 97702"], cache, fetcher=fake_fetch, delay=0)
    assert seen[0].startswith(NOMINATIM_URL)
    assert "Duck+Call+Lane" in seen[0] or "Duck%20Call%20Lane" in seen[0]
    assert "format=jsonv2" in seen[0]


def empty_for_provider(url):
    """An empty result in whichever shape the provider being called returns."""
    if "nominatim" in url:
        return "[]"
    return json.dumps({"result": {"addressMatches": []}})


def test_no_result_is_recorded_as_a_failure_not_retried(tmp_path):
    calls = []

    def fake_fetch(url, **kwargs):
        calls.append(url)
        return empty_for_provider(url)

    cache = GeocodeCache(tmp_path / "geocode.json")
    geocode_all(["Nowhere Rd, Bend OR 97701"], cache, fetcher=fake_fetch, delay=0)
    first_pass = len(calls)
    geocode_all(["Nowhere Rd, Bend OR 97701"], cache, fetcher=fake_fetch, delay=0)
    # The second pass must add nothing: the miss is cached across all providers.
    assert len(calls) == first_pass
    assert cache.get("Nowhere Rd, Bend OR 97701") == (UNKNOWN, UNKNOWN)


def test_unknown_addresses_are_never_sent_to_nominatim(tmp_path):
    calls = []

    def fake_fetch(url, **kwargs):
        calls.append(url)
        return "[]"

    cache = GeocodeCache(tmp_path / "geocode.json")
    geocode_all([UNKNOWN, ""], cache, fetcher=fake_fetch, delay=0)
    assert calls == []


def test_a_network_error_does_not_abort_the_whole_batch(tmp_path):
    def flaky(url, **kwargs):
        if "Bad" in url:
            raise RuntimeError("boom")
        return json.dumps([{"lat": "44.0", "lon": "-121.0"}])

    cache = GeocodeCache(tmp_path / "geocode.json")
    geocode_all(["Bad St, Bend OR 97701", "Good St, Bend OR 97701"],
                cache, fetcher=flaky, delay=0)
    assert cache.get("Good St, Bend OR 97701") == ("44.0", "-121.0")
    # The failure is not cached as a permanent negative — it may be transient.
    assert not cache.knows("Bad St, Bend OR 97701")


@pytest.mark.parametrize("address,expected", [
    ("1025 NE Rambling Ln. - #2, Bend, OR 97701", "1025 NE Rambling Ln., Bend, OR 97701"),
    ("20077 Beth Ave Unit 3, Bend, OR 97702", "20077 Beth Ave, Bend, OR 97702"),
    ("1398 NE Elk Ct #1 , Bend, OR 97701", "1398 NE Elk Ct, Bend, OR 97701"),
    ("1529 NW Portland Ave - B, Bend, OR 97701", "1529 NW Portland Ave, Bend, OR 97701"),
    ("21177 SE Azalia Ave., Bend, OR 97702", "21177 SE Azalia Ave., Bend, OR 97702"),
])
def test_street_address_strips_unit_designators(address, expected):
    from bendrentals.geocode import street_address
    assert street_address(address) == expected


def test_falls_back_to_the_street_address_when_the_unit_is_not_found(tmp_path):
    seen = []

    def fake_fetch(url, **kwargs):
        seen.append(url)
        # The unit-qualified query finds nothing; the building does.
        if "%232" in url or "#2" in url:
            return "[]"
        return json.dumps([{"lat": "44.05", "lon": "-121.30"}])

    cache = GeocodeCache(tmp_path / "geocode.json")
    geocode_all(["1025 NE Rambling Ln. - #2, Bend, OR 97701"], cache,
                fetcher=fake_fetch, delay=0)
    assert len(seen) == 2
    # Coordinates are stored against the ORIGINAL address, units included.
    assert cache.get("1025 NE Rambling Ln. - #2, Bend, OR 97701") == ("44.05", "-121.30")


def test_no_unit_variant_request_when_there_is_no_unit_to_strip(tmp_path):
    seen = []

    def fake_fetch(url, **kwargs):
        seen.append(url)
        return empty_for_provider(url)

    cache = GeocodeCache(tmp_path / "geocode.json")
    geocode_all(["21177 SE Azalia Ave., Bend, OR 97702"], cache, fetcher=fake_fetch, delay=0)
    # One Nominatim try and one Census try -- no unit-stripped duplicates.
    assert len(seen) == 2
    assert sum(1 for u in seen if "nominatim" in u) == 1


def test_census_is_tried_after_nominatim_misses(tmp_path):
    from bendrentals.geocode import CENSUS_URL

    seen = []

    def fake_fetch(url, **kwargs):
        seen.append(url)
        if "nominatim" in url:
            return "[]"                      # OSM has never heard of it
        return json.dumps({"result": {"addressMatches": [
            {"coordinates": {"x": -121.26521, "y": 44.04389}}]}})

    cache = GeocodeCache(tmp_path / "geocode.json")
    geocode_all(["21177 SE Azalia Ave., Bend, OR 97702"], cache,
                fetcher=fake_fetch, delay=0)
    assert any(u.startswith(CENSUS_URL) for u in seen)
    # Census returns x=lon, y=lat — the order must not be swapped.
    assert cache.get("21177 SE Azalia Ave., Bend, OR 97702") == ("44.04389", "-121.26521")


def test_census_is_not_called_when_nominatim_succeeds(tmp_path):
    seen = []

    def fake_fetch(url, **kwargs):
        seen.append(url)
        return json.dumps([{"lat": "44.0", "lon": "-121.0"}])

    cache = GeocodeCache(tmp_path / "geocode.json")
    geocode_all(["1 Somewhere St, Bend, OR 97701"], cache, fetcher=fake_fetch, delay=0)
    assert not any("census" in u for u in seen)


def test_failure_is_only_recorded_after_every_provider_misses(tmp_path):
    def always_empty(url, **kwargs):
        if "nominatim" in url:
            return "[]"
        return json.dumps({"result": {"addressMatches": []}})

    cache = GeocodeCache(tmp_path / "geocode.json")
    geocode_all(["Nowhere At All, Bend, OR 97701"], cache,
                fetcher=always_empty, delay=0)
    assert cache.get("Nowhere At All, Bend, OR 97701") == (UNKNOWN, UNKNOWN)
