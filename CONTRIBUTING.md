# Contributing

Issues and pull requests are welcome. The most useful report is a source that
has started returning fewer listings than its own site shows: that means its
markup changed and a parser needs updating.

## Reporting a broken source

Include the company, and what `scrape.py` printed for it:

```bash
python scrape.py <site-key>       # the keys are the [sites.*] names in sites.toml
```

`Parsed 4/7 listings` means the page changed shape. `No listings found` means
it changed more than that.

## Suggesting a source

You do not have to write anything. A link to a Bend property manager's rentals
page, in an issue, is enough — working out where the data actually lives is
the interesting part and it can be done from here.

Worth knowing before you suggest one: what matters is not the company's
website but the platform underneath it. Nine of the thirteen sources here are
AppFolio portals reached through a "Tenant Portal" or "Pay Rent" link, because
the company's own page renders its listings with JavaScript and serves HTML
containing none of them. So a site that looks unscrapable often is not.

## Adding a source

If you would rather do the work: most new sources need a `sites.toml` entry
and no code at all, because nine of the thirteen already here run on the same
platform.

1. Find where the data really is. If the company's page renders with
   JavaScript, look for a tenant subdomain (its "Tenant Portal" or "Pay Rent"
   link usually points at one) or for the endpoint its own widget reads. Both
   are normally server-rendered.
2. Work out the site's URL filters before writing any parser. Filtering at the
   source beats discarding rows afterwards.
3. Save fixture HTML into `tests/fixtures/<key>/`, then strip it (below).
   Every test runs offline, and no test may reach the network.
4. Reuse an existing `structure` and `title_format` if either fits. Write a new
   module only when the platform or the title convention is genuinely new.
5. Set `status = "ready"` in `sites.toml` once its parser works.

## House rules

These are the ones worth knowing before changing anything:

- `"?"` means the source did not say it. An empty cell always means a bug.
  Never write `""` for missing source data.
- Never drop a listing you could not parse. Write it with
  `parse_status = "partial"` and warn on stderr.
- Never infer a pet policy from silence. A dogs-only policy leaves cats
  unknown.
- Keep the request delays. `appfolio.com` publishes `Crawl-delay: 10` and gets
  it; the geocoders are slower still.
- No email address goes into a User-Agent, a request, or the committed data.
- Third-party contact details in test fixtures are placeholders. Please keep
  them that way when refreshing a fixture.

## Refreshing a fixture

A captured Squarespace or Divi page is mostly framework: bundled JavaScript,
stylesheets, base64 image payloads, a dozen CDN variants of every photo, and
runs of hundreds of spaces. None of it is content, and all of it would sit in
git history forever — stripping took this fixture set from 4.4 MB to 1.1 MB
without changing a single parsed value.

So after saving a page, strip it, and prove the strip was invisible:

```bash
python -m tools.parse_snapshot before.json    # what the parsers read now
python -m tools.strip_fixtures                # remove what none of them read
python -m tools.parse_snapshot after.json
diff before.json after.json                   # must be empty
```

`parse_snapshot` captures every value all five parsers can extract, which is
more than the tests assert. An empty diff is the evidence; a non-empty one
means a stage took something real, and
`python -m tools.strip_fixtures <stage>` will say which.

## Tests

```bash
python -m pytest
```

They run against the saved fixtures, so they are the same offline and cannot
be flaky. A change to a parser wants a fixture-backed test alongside it.
