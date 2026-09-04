from bendrentals.models import UNKNOWN, Listing, google_maps_link


def test_unknown_sentinel_is_question_mark():
    assert UNKNOWN == "?"


def test_fieldnames_are_in_csv_order():
    assert Listing.fieldnames() == [
        "company", "link", "address", "region", "price", "bedrooms",
        "bathrooms", "sqft", "property_type", "available", "available_now",
        "cats_allowed", "dogs_allowed", "maps_link", "lat", "lon", "summary",
        "pets_raw", "scraped_at", "parse_status",
    ]


def test_the_long_description_is_not_a_stored_field():
    """It is read while parsing, for bathrooms and pets, then discarded.

    `summary` is the only prose the CSV keeps, so the published data stays a
    table of facts rather than a copy of someone else's marketing text.
    """
    assert "description" not in Listing.fieldnames()


def make_listing(**overrides):
    fields = dict(
        company="Trailhead Property Management",
        link="https://example.com/a", price=3550, bedrooms=3,
        bathrooms="2.5", sqft=2472, property_type=UNKNOWN,
        available="2026-09-15", available_now="False",
        region="SW Bend", address="19884 Duck Call Lane, Bend OR 97702",
        cats_allowed="True", dogs_allowed="False", lat="44.0", lon="-121.3",
        maps_link="https://maps", summary="Amazing home", pets_raw=UNKNOWN,
        scraped_at="2026-08-31T14:22:07", parse_status="ok",
    )
    fields.update(overrides)
    return Listing(**fields)


def test_to_row_returns_every_field():
    row = make_listing().to_row()
    assert set(row) == set(Listing.fieldnames())
    assert row["price"] == 3550
    assert row["pets_raw"] == "?"


def test_cats_and_dogs_are_independent_fields():
    row = make_listing(cats_allowed="True", dogs_allowed=UNKNOWN).to_row()
    assert row["cats_allowed"] == "True"
    assert row["dogs_allowed"] == "?"


def test_company_identifies_the_source_in_the_shared_csv():
    assert make_listing().to_row()["company"] == "Trailhead Property Management"


def test_google_maps_link_encodes_address():
    assert google_maps_link("19884 Duck Call Lane, Bend OR 97702") == (
        "https://www.google.com/maps/search/?api=1"
        "&query=19884+Duck+Call+Lane%2C+Bend+OR+97702"
    )


def test_google_maps_link_passes_unknown_through():
    assert google_maps_link(UNKNOWN) == UNKNOWN
