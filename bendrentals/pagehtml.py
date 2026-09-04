"""Map records -> one self-contained HTML page.

The page embeds its data rather than fetching it. A page opened from `file://`
cannot read a sibling file — browsers treat that as cross-origin — so a single
file can be double-clicked and simply works, on GitHub Pages and off it alike.

Nothing here interpolates listing text into markup. Values reach the page only
inside the JSON block that `mapdata.embed_json` has escaped, and the script
writes them with `textContent`, so a listing summary can never become HTML.
Link hrefs are restricted to http(s) in Python before they are ever set.

The document is a template with `__TOKEN__` placeholders rather than an
f-string: the page is mostly CSS and JavaScript, and doubling every brace to
escape it made the source unreadable and the mistakes invisible.
"""

from datetime import datetime
from html import escape

from .mapdata import (
    FACET_FIELDS, PRICE_BANDS, RANGE_FIELDS, UNKNOWN_BAND, embed_json, facets,
    ranges,
)

LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"

#: Linked from the header icon.
REPO_URL = "https://github.com/NBPub/bend_rentals"

#: Sits beside the page in docs/. Relative, so it resolves both on Pages and
#: when the file is opened directly; writing the page elsewhere with --out
#: simply leaves the browser without an icon.
FAVICON = "favicon.png"

#: Tile providers, keyed by the name `build_page.py --tiles` takes.
#:
#: The default is deliberately not OpenStreetMap's own servers. Their tile
#: usage policy requires a Referer, and a page opened from file:// sends none,
#: so OSM returns a "blocked" image instead of a map. Served over https from
#: GitHub Pages it would work; one default that works everywhere is simpler.
#:
#: Esri and CARTO both work with no key. CARTO renders OSM data (so OSM keeps
#: the credit) but watermarks its free tier; Esri's World Street Map is Esri's
#: own cartography, credited to them alone. Attribution is not interchangeable.
TILE_PROVIDERS = {
    "carto-light": {
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "subdomains": "abcd",
        "attribution": ('&copy; <a href="https://www.openstreetmap.org/copyright">'
                        'OpenStreetMap</a> contributors &copy; '
                        '<a href="https://carto.com/attributions">CARTO</a>'),
    },
    "carto-voyager": {
        "url": "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        "subdomains": "abcd",
        "attribution": ('&copy; <a href="https://www.openstreetmap.org/copyright">'
                        'OpenStreetMap</a> contributors &copy; '
                        '<a href="https://carto.com/attributions">CARTO</a>'),
    },
    "esri": {
        "url": ("https://server.arcgisonline.com/ArcGIS/rest/services/"
                "World_Street_Map/MapServer/tile/{z}/{y}/{x}"),
        "subdomains": "",
        "attribution": "Tiles &copy; Esri",
    },
    # Only usable when the page is served over http(s); see the note above.
    "osm": {
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "subdomains": "abc",
        "attribution": ('&copy; <a href="https://www.openstreetmap.org/copyright">'
                        'OpenStreetMap</a> contributors'),
    },
}

#: Esri by default: no Referer requirement and no watermark.
DEFAULT_TILES = "esri"

#: Column headings, and the labels the filter panel uses for each field.
FIELD_LABELS = {
    "company": "Company",
    "address": "Address",
    "region": "Region",
    "price": "Price",
    "bedrooms": "Beds",
    "bathrooms": "Baths",
    "sqft": "Sq Ft",
    "available": "Available",
    "available_now": "Available now",
    "cats_allowed": "Cats",
    "dogs_allowed": "Dogs",
    "summary": "Summary",
    "link": "Listing",
    "maps_link": "Map",
}

#: Table columns, in order. `maps_link` is absent because the map link is
#: rendered inside the address cell rather than taking a column of its own.
TABLE_FIELDS = (
    "company", "link", "address", "region", "price", "bedrooms", "bathrooms",
    "sqft", "available", "available_now", "cats_allowed", "dogs_allowed",
    "summary",
)

#: Shown in a marker popup when present, in this order. The address is the
#: heading, so it is not repeated here.
POPUP_FIELDS = ("region", "price", "bedrooms", "bathrooms", "sqft",
                "available", "cats_allowed", "dogs_allowed", "company")

#: Rendered as a link rather than as text.
LINK_FIELDS = ("link", "maps_link")

#: Rendered as a tick or a cross rather than the words True and False.
BOOLEAN_FIELDS = ("cats_allowed", "dogs_allowed", "available_now")

#: Given its own column on the right of the filter panel. Thirteen long names
#: crowd the other filters when they share the same grid.
SIDE_FACET = "company"

#: Where the page sends anyone who wants the data rather than the view.
DEFAULT_CSV_URL = (
    "https://raw.githubusercontent.com/NBPub/bend_rentals/main/data/listings.csv"
)


def render(records, unmapped=(), *, generated_at=None, title="Rentals in Bend, OR",
           tiles=DEFAULT_TILES, csv_url=DEFAULT_CSV_URL, repo_url=REPO_URL) -> str:
    """One complete HTML document: map, filters and table."""
    generated_at = generated_at or datetime.now()

    if tiles not in TILE_PROVIDERS:
        raise ValueError(
            f"Unknown tile provider {tiles!r}. "
            f"Choose one of: {', '.join(sorted(TILE_PROVIDERS))}."
        )
    provider = TILE_PROVIDERS[tiles]
    # Suggested in the failure banner; never the one that just failed, and
    # never "osm", which cannot work from a local file at all.
    alternative = next(n for n in TILE_PROVIDERS if n not in (tiles, "osm"))

    records, unmapped = list(records), list(unmapped)
    everything = records + unmapped

    payload = {
        "records": records,
        "unmapped": unmapped,
        "facets": facets(everything),
        "ranges": ranges(everything),
        "bands": list(PRICE_BANDS) + [UNKNOWN_BAND],
        "labels": FIELD_LABELS,
        "facetFields": [f for f in FACET_FIELDS if f != SIDE_FACET],
        "sideFacet": SIDE_FACET,
        "rangeFields": list(RANGE_FIELDS),
        "tableFields": list(TABLE_FIELDS),
        "popupFields": list(POPUP_FIELDS),
        "linkFields": list(LINK_FIELDS),
        "booleanFields": list(BOOLEAN_FIELDS),
        "tiles": provider,
        "alternative": alternative,
        "csvUrl": _safe(csv_url),
        "generated": generated_at.strftime("%Y-%m-%d %H:%M"),
        "total": len(everything),
    }

    return (TEMPLATE
            .replace("__TITLE__", escape(title))
            .replace("__REPO_URL__", escape(_safe(repo_url), quote=True))
            .replace("__FAVICON__", escape(FAVICON, quote=True))
            .replace("__LEAFLET_CSS__", LEAFLET_CSS)
            .replace("__LEAFLET_JS__", LEAFLET_JS)
            .replace("__PAYLOAD__", embed_json(payload)))


def _safe(url: str) -> str:
    """An http(s) URL, or "". The page renders no link it cannot vouch for."""
    return url if (url or "").startswith(("http://", "https://")) else ""


#: GitHub's own mark, inline so the page needs nothing from the network for it.
GITHUB_MARK = (
    '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" '
    'fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 '
    '3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04'
    '-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7'
    'c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 '
    '1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466'
    '-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105'
    '-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04'
    '.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 '
    '3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36'
    '.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 '
    '22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>'
)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="icon" type="image/png" href="__FAVICON__">
<link rel="apple-touch-icon" href="__FAVICON__">
<link rel="stylesheet" href="__LEAFLET_CSS__">
<style>
  :root {
    color-scheme: light dark;
    --line: rgba(128,128,128,.32);
    --muted: #6b7280;
    --panel: rgba(128,128,128,.07);
    /* The middle of the price ramp in mapdata.PRICE_BANDS, so the controls
       belong to the same palette as the markers they filter. */
    --accent: #2c7fb8;
    --yes: #1a7f37;
    --no: #b3261e;
    --pop: #8a7420;          /* khaki, for the links under the map */
  }
  @media (prefers-color-scheme: dark) {
    :root { --yes: #3fb950; --no: #f85149; --pop: #d9c56a; --accent: #41b6c4; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  a { color: inherit; }
  input[type=checkbox] { accent-color: var(--accent); }

  header { border-bottom: 1px solid var(--line); }
  .titlebar, .statusbar {
    padding: .5rem 1rem; display: flex; flex-wrap: wrap;
    gap: .4rem 1.1rem; align-items: center;
  }
  .titlebar { padding-bottom: .1rem; }
  .statusbar { padding-top: 0; align-items: baseline; }
  h1 { font-size: 1.15rem; margin: 0; font-weight: 600; }
  .gh { display: inline-flex; color: var(--muted); text-decoration: none; }
  .gh:hover { color: inherit; }
  .jump { font-size: .82rem; color: var(--accent); font-weight: 600;
          text-decoration: none; }
  .jump:hover { text-decoration: underline; }
  .meta { color: var(--muted); font-size: .82rem; }
  .key { display: inline-flex; align-items: center; gap: .3rem; font-size: .8rem; }
  .key i { width: .7rem; height: .7rem; border-radius: 50%; display: inline-block; }
  #legend { display: flex; flex-wrap: wrap; gap: .3rem .85rem; }

  button {
    font: inherit; padding: .2rem .55rem; border: 1px solid var(--line);
    border-radius: .3rem; background: transparent; cursor: pointer; color: inherit;
  }
  button:hover { background: var(--panel); }

  #filters {
    padding: .7rem 1rem; border-bottom: 1px solid var(--line);
    background: var(--panel);
    display: grid; gap: .8rem 1.4rem;
    grid-template-columns: minmax(0, 1fr) minmax(180px, 15rem);
  }
  #filters-main {
    display: grid; gap: .8rem 1.4rem;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    align-content: start;
  }
  #filters-side { border-left: 1px solid var(--line); padding-left: 1.1rem; }
  @media (max-width: 700px) {
    #filters { grid-template-columns: 1fr; }
    #filters-side { border-left: 0; padding-left: 0;
                    border-top: 1px solid var(--line); padding-top: .7rem; }
  }
  fieldset { border: 0; margin: 0; padding: 0; min-width: 0; }
  legend { font-weight: 600; font-size: .8rem; padding: 0 0 .25rem; }
  .opts { display: flex; flex-wrap: wrap; gap: .1rem .8rem;
          max-height: 9rem; overflow-y: auto; }
  #filters-side .opts { flex-direction: column; flex-wrap: nowrap; max-height: 13rem; }
  label { display: inline-flex; align-items: center; gap: .3rem;
          font-size: .82rem; cursor: pointer; }
  .range { display: flex; align-items: center; gap: .35rem; font-size: .82rem; }
  .range input { width: 5.5rem; font: inherit; padding: .15rem .3rem;
                 border: 1px solid var(--line); border-radius: .25rem;
                 background: transparent; color: inherit; }
  .actions { display: flex; align-items: flex-end; gap: .5rem; }

  #map { height: 66vh; min-height: 340px; scroll-margin-top: .5rem; }
  .warn { background: #fff3cd; color: #664d03; padding: .6rem 1rem;
          font-size: .85rem; border-bottom: 1px solid #ffe69c; }

  .pop { min-width: 220px; max-width: 280px; }
  .pop h2 { font-size: .92rem; margin: 0 0 .4rem; }
  .pop dl { display: grid; grid-template-columns: auto 1fr; gap: .1rem .6rem; margin: 0 0 .45rem; }
  .pop dt { color: var(--muted); }
  .pop dd { margin: 0; }
  .pop p { margin: 0 0 .45rem; color: var(--muted); }
  .pop a { display: inline-block; margin-right: .7rem; }

  section { padding: .9rem 1rem 1.4rem; scroll-margin-top: .5rem; }
  section h2 { font-size: .95rem; margin: 0 0 .3rem; }
  #unmapped ul { margin: .4rem 0 0; padding-left: 1.1rem; }
  #unmapped li { margin-bottom: .3rem; }
  #unmapped a { color: var(--pop); font-weight: 600; }
  #unmapped .sep { color: var(--muted); }

  .tablehead { display: flex; flex-wrap: wrap; gap: .4rem 1rem;
               align-items: baseline; margin-bottom: .5rem; }
  .scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: .35rem; }
  table { border-collapse: collapse; width: 100%; font-size: .82rem; }
  th, td { text-align: left; padding: .3rem .55rem; border-bottom: 1px solid var(--line);
           white-space: nowrap; vertical-align: top; }
  th { position: sticky; top: 0; background: Canvas; padding: 0; }
  th button { width: 100%; border: 0; border-radius: 0; text-align: left;
              padding: .35rem .55rem; font-weight: 600; }
  td.wrap { white-space: normal; min-width: 15rem; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  td .maplink { color: var(--accent); margin-left: .4rem; font-size: .95em; }
  .yes { color: var(--yes); font-weight: 700; }
  .no { color: var(--no); font-weight: 700; }
  .empty { color: var(--muted); padding: .8rem; }
</style>
</head>
<body>
<header>
  <div class="titlebar">
    <h1>__TITLE__</h1>
    <a class="gh" id="repo" href="__REPO_URL__" target="_blank"
       rel="noopener noreferrer" title="Source on GitHub"
       aria-label="Source on GitHub">__GITHUB_MARK__</a>
  </div>
  <div class="statusbar">
    <a class="jump" href="#tablewrap">Data table &#8595;</a>
    <span class="meta" id="count"></span>
    <span id="legend"></span>
    <button type="button" id="fit">Fit map to results</button>
  </div>
</header>

<div id="filters">
  <div id="filters-main"></div>
  <div id="filters-side"></div>
</div>
<div id="map"></div>
<section id="unmapped"></section>

<section id="tablewrap">
  <div class="tablehead">
    <h2 id="tabletitle">Listings</h2>
    <span class="meta" id="csvlink"></span>
    <a class="jump" href="#map">Map &#8593;</a>
  </div>
  <div class="scroll"><table><thead><tr id="head"></tr></thead><tbody id="body"></tbody></table></div>
  <p class="meta" id="tablenote"></p>
</section>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script src="__LEAFLET_JS__"></script>
<script>
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById('payload').textContent);
  var ALL = D.records.concat(D.unmapped);
  var EVERY_FACET = D.facetFields.concat([D.sideFacet]);

  // "NW Bend" -> "Bend", from the region facet Python built. A listing known
  // only to be "in Bend" could be in any Bend quadrant, so it must not vanish
  // when someone filters to one.
  var cityOf = {};
  (D.facets.region || []).forEach(function (o) { cityOf[o.value] = o.city; });

  var selected = {};                      // field -> Set of ticked values
  EVERY_FACET.forEach(function (f) {
    selected[f] = new Set((D.facets[f] || []).map(function (o) { return o.value; }));
  });
  var bounds = {};                        // field -> {min, max} as typed
  D.rangeFields.forEach(function (f) { bounds[f] = { min: null, max: null }; });
  var sort = { field: 'price', dir: 1 };

  function isBlank(v) { return v === '' || v === null || v === undefined; }

  // The key a tick-box is stored under. Python writes the same spelling --
  // see mapdata.facet_value -- so a studio's 0 bedrooms stays "0" and does
  // not collapse into the "not stated" box.
  function key(v) { return isBlank(v) ? '' : String(v); }

  function regionOk(rec) {
    var chosen = selected.region;
    var own = key(rec.region);
    if (chosen.has(own)) return true;
    // The listing names a city with no quadrant: keep it if any quadrant of
    // that same city is chosen, because it could be in any of them.
    if (own && cityOf[own] === own) {
      var hit = false;
      chosen.forEach(function (v) { if (cityOf[v] === own) hit = true; });
      return hit;
    }
    return false;
  }

  function matches(rec) {
    for (var i = 0; i < EVERY_FACET.length; i++) {
      var f = EVERY_FACET[i];
      if (!selected[f]) continue;
      if (f === 'region') { if (!regionOk(rec)) return false; continue; }
      if (!selected[f].has(key(rec[f]))) return false;
    }
    for (var j = 0; j < D.rangeFields.length; j++) {
      var g = D.rangeFields[j], b = bounds[g], v = rec[g];
      if (b.min === null && b.max === null) continue;
      // A listing whose value the site never stated is kept: a range filter
      // says what we want, not that an unknown is disqualified.
      if (typeof v !== 'number') continue;
      if (b.min !== null && v < b.min) return false;
      if (b.max !== null && v > b.max) return false;
    }
    return true;
  }

  function fmt(field, value) {
    if (isBlank(value)) return '\\u2014';
    if (field === 'price') return '$' + value.toLocaleString();
    if (field === 'sqft') return value.toLocaleString();
    return String(value);
  }

  // True/False reads as data; a tick and a cross read at a glance. "?" stays
  // a dash, because the site not saying is not the same as a no.
  function boolCell(value) {
    var span = document.createElement('span');
    if (value === 'True') { span.className = 'yes'; span.textContent = '\\u2713'; }
    else if (value === 'False') { span.className = 'no'; span.textContent = '\\u2717'; }
    else { span.textContent = '\\u2014'; }
    return span;
  }

  function anchor(href, text, className) {
    var a = document.createElement('a');
    a.href = href;                       // already restricted to http(s) in Python
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = text;
    if (className) a.className = className;
    return a;
  }

  // ---- filter panel -------------------------------------------------------
  function facetBox(field, host) {
    var options = D.facets[field] || [];
    if (options.length < 2) return;    // a filter with one choice filters nothing
    var set = document.createElement('fieldset');
    var cap = document.createElement('legend');
    cap.textContent = D.labels[field] || field;
    set.appendChild(cap);
    var box = document.createElement('div');
    box.className = 'opts';
    options.forEach(function (opt) {
      var label = document.createElement('label');
      var input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = true;
      input.addEventListener('change', function () {
        if (input.checked) selected[field].add(opt.value);
        else selected[field].delete(opt.value);
        apply();
      });
      label.appendChild(input);
      label.appendChild(document.createTextNode(opt.label));
      box.appendChild(label);
    });
    set.appendChild(box);
    host.appendChild(set);
  }

  function buildFilters() {
    var main = document.getElementById('filters-main');
    var side = document.getElementById('filters-side');

    D.rangeFields.forEach(function (field) {
      var r = D.ranges[field] || {};
      if (r.min === null || r.min === undefined) return;   // nothing to filter
      var set = document.createElement('fieldset');
      var cap = document.createElement('legend');
      cap.textContent = D.labels[field] || field;
      set.appendChild(cap);
      var row = document.createElement('div');
      row.className = 'range';
      ['min', 'max'].forEach(function (which, idx) {
        var input = document.createElement('input');
        input.type = 'number';
        input.placeholder = Math.round(which === 'min' ? r.min : r.max);
        input.setAttribute('aria-label', (D.labels[field] || field) + ' ' + which);
        input.addEventListener('input', function () {
          var raw = input.value.trim();
          bounds[field][which] = raw === '' ? null : Number(raw);
          apply();
        });
        if (idx) row.appendChild(document.createTextNode('to'));
        row.appendChild(input);
      });
      set.appendChild(row);
      main.appendChild(set);
    });

    D.facetFields.forEach(function (field) { facetBox(field, main); });
    facetBox(D.sideFacet, side);

    var actions = document.createElement('div');
    actions.className = 'actions';
    var reset = document.createElement('button');
    reset.type = 'button';
    reset.textContent = 'Reset filters';
    reset.addEventListener('click', function () {
      document.querySelectorAll('#filters input[type=checkbox]').forEach(
        function (i) { i.checked = true; });
      document.querySelectorAll('#filters input[type=number]').forEach(
        function (i) { i.value = ''; });
      EVERY_FACET.forEach(function (f) {
        selected[f] = new Set((D.facets[f] || []).map(function (o) { return o.value; }));
      });
      D.rangeFields.forEach(function (f) { bounds[f] = { min: null, max: null }; });
      apply();
    });
    actions.appendChild(reset);
    main.appendChild(actions);
  }

  // ---- map ----------------------------------------------------------------
  var map = L.map('map');
  var layer = L.layerGroup().addTo(map);
  var tiles = L.tileLayer(D.tiles.url, {
    maxZoom: 19,
    subdomains: D.tiles.subdomains || 'abc',
    attribution: D.tiles.attribution
  }).addTo(map);

  // A blocked or unreachable tile server otherwise leaves a silent grey void.
  // OpenStreetMap's own servers do exactly this for a page opened from file://,
  // because their usage policy requires a Referer and there is none to send.
  var tileFailures = 0;
  tiles.on('tileerror', function () {
    if (++tileFailures !== 3) return;
    var note = document.createElement('div');
    note.className = 'warn';
    note.textContent = 'Map tiles failed to load. Rebuild the page with a '
      + 'different provider, for example:  build_page.py --tiles ' + D.alternative;
    document.getElementById('map').before(note);
  });

  // Every value below is written with textContent or set as a property, never
  // as HTML, so listing text cannot become markup.
  function popup(rec) {
    var box = document.createElement('div');
    box.className = 'pop';

    var heading = document.createElement('h2');
    heading.textContent = rec.address || 'Listing';
    box.appendChild(heading);

    var list = document.createElement('dl');
    D.popupFields.forEach(function (field) {
      if (isBlank(rec[field])) return;
      var term = document.createElement('dt');
      term.textContent = D.labels[field] || field;
      var detail = document.createElement('dd');
      if (D.booleanFields.indexOf(field) >= 0) detail.appendChild(boolCell(rec[field]));
      else detail.textContent = fmt(field, rec[field]);
      list.appendChild(term);
      list.appendChild(detail);
    });
    box.appendChild(list);

    if (rec.summary) {
      var blurb = document.createElement('p');
      blurb.textContent = rec.summary;
      box.appendChild(blurb);
    }

    if (rec.link) box.appendChild(anchor(rec.link, 'View listing'));
    if (rec.maps_link) box.appendChild(anchor(rec.maps_link, 'Open in Maps'));
    return box;
  }

  var lastPoints = [];
  function drawMap(rows) {
    layer.clearLayers();
    lastPoints = [];
    rows.forEach(function (rec) {
      if (typeof rec.lat !== 'number' || typeof rec.lon !== 'number') return;
      L.circleMarker([rec.lat, rec.lon], {
        radius: 7, weight: 2, color: '#ffffff', opacity: .9,
        fillColor: rec.band.colour, fillOpacity: .95
      }).addTo(layer).bindPopup(popup(rec));
      lastPoints.push([rec.lat, rec.lon]);
    });
  }

  function fitMap() {
    if (lastPoints.length) map.fitBounds(lastPoints, { padding: [40, 40] });
    else map.setView([44.058, -121.315], 12);          // Bend, with nothing to fit
  }
  document.getElementById('fit').addEventListener('click', fitMap);

  // ---- legend -------------------------------------------------------------
  function drawLegend(rows) {
    var host = document.getElementById('legend');
    host.textContent = '';
    D.bands.forEach(function (band) {
      var n = rows.filter(function (r) { return r.band.label === band.label; }).length;
      if (!n) return;
      var span = document.createElement('span');
      span.className = 'key';
      var swatch = document.createElement('i');
      swatch.style.background = band.colour;
      span.appendChild(swatch);
      span.appendChild(document.createTextNode(band.label + ' '));
      var count = document.createElement('b');
      count.textContent = String(n);
      span.appendChild(count);
      host.appendChild(span);
    });
  }

  // ---- listings without coordinates ---------------------------------------
  function drawUnmapped(rows) {
    var host = document.getElementById('unmapped');
    host.textContent = '';
    if (!rows.length) return;

    var heading = document.createElement('h2');
    heading.textContent = 'Not mappable (' + rows.length + ')';
    host.appendChild(heading);

    var note = document.createElement('p');
    note.className = 'meta';
    note.textContent = 'Coordinates not found for the following listings.';
    host.appendChild(note);

    var list = document.createElement('ul');
    rows.forEach(function (rec) {
      var item = document.createElement('li');
      var specs = [
        rec.bedrooms ? rec.bedrooms + ' bd' : '',
        rec.bathrooms ? rec.bathrooms + ' ba' : '',
        rec.sqft ? rec.sqft.toLocaleString() + ' sqft' : ''
      ].filter(Boolean).join(' / ');
      var label = [
        rec.address || 'No address published',
        specs,
        typeof rec.price === 'number' ? '$' + rec.price.toLocaleString() : '',
        rec.company
      ].filter(Boolean).join(' \\u2014 ');
      item.textContent = label;

      var links = [];
      if (rec.link) links.push(anchor(rec.link, 'view'));
      if (rec.maps_link) links.push(anchor(rec.maps_link, 'map'));
      links.forEach(function (link, i) {
        if (i) {
          // The divider stays outside the anchors, so it reads as a separator
          // rather than as part of either link.
          var sep = document.createElement('span');
          sep.className = 'sep';
          sep.textContent = '|';
          item.appendChild(document.createTextNode(' '));
          item.appendChild(sep);
        }
        item.appendChild(document.createTextNode(' '));
        item.appendChild(link);
      });
      list.appendChild(item);
    });
    host.appendChild(list);
  }

  // ---- table --------------------------------------------------------------
  function compare(a, b) {
    var f = sort.field, av = a[f], bv = b[f];
    var ab = isBlank(av), bb = isBlank(bv);
    if (ab && bb) return 0;
    if (ab) return 1;                    // blanks last, whichever way we sort
    if (bb) return -1;
    var r;
    if (typeof av === 'number' && typeof bv === 'number') r = av - bv;
    else r = String(av).localeCompare(String(bv), undefined, { numeric: true });
    return r * sort.dir;
  }

  function buildHead() {
    var row = document.getElementById('head');
    row.textContent = '';
    D.tableFields.forEach(function (field) {
      var cell = document.createElement('th');
      var button = document.createElement('button');
      button.type = 'button';
      button.dataset.field = field;
      button.addEventListener('click', function () {
        if (sort.field === field) sort.dir = -sort.dir;
        else { sort.field = field; sort.dir = 1; }
        apply();
      });
      cell.appendChild(button);
      row.appendChild(cell);
    });
  }

  function labelHead() {
    document.querySelectorAll('#head button').forEach(function (button) {
      var field = button.dataset.field;
      var arrow = sort.field === field ? (sort.dir === 1 ? ' \\u2191' : ' \\u2193') : '';
      button.textContent = (D.labels[field] || field) + arrow;
    });
  }

  function cellFor(rec, field) {
    var td = document.createElement('td');

    if (D.linkFields.indexOf(field) >= 0) {
      if (rec[field]) td.appendChild(anchor(rec[field], 'open'));
      else td.textContent = '\\u2014';
      return td;
    }
    if (D.booleanFields.indexOf(field) >= 0) {
      td.appendChild(boolCell(rec[field]));
      return td;
    }
    if (field === 'address') {
      td.className = 'wrap';
      td.textContent = fmt(field, rec.address);
      // The map link rides along with the address rather than taking a column.
      if (rec.maps_link) td.appendChild(anchor(rec.maps_link, 'map', 'maplink'));
      return td;
    }
    if (typeof rec[field] === 'number') {
      td.className = 'num';
      td.textContent = fmt(field, rec[field]);
      return td;
    }
    if (field === 'summary') td.className = 'wrap';
    td.textContent = fmt(field, rec[field]);
    return td;
  }

  function drawTable(rows) {
    labelHead();
    var body = document.getElementById('body');
    body.textContent = '';
    rows.slice().sort(compare).forEach(function (rec) {
      var tr = document.createElement('tr');
      D.tableFields.forEach(function (field) { tr.appendChild(cellFor(rec, field)); });
      body.appendChild(tr);
    });

    var note = document.getElementById('tablenote');
    note.textContent = rows.length ? '' :
      'No listings match these filters. Try Reset filters.';
  }

  // ---- wiring -------------------------------------------------------------
  function apply() {
    var kept = ALL.filter(matches);
    var mappable = kept.filter(function (r) { return typeof r.lat === 'number'; });
    var rest = kept.filter(function (r) { return typeof r.lat !== 'number'; });

    document.getElementById('count').textContent =
      kept.length + ' of ' + D.total + ' listings \\u00b7 ' + mappable.length
      + ' mapped \\u00b7 updated ' + D.generated;
    document.getElementById('tabletitle').textContent = 'Listings (' + kept.length + ')';

    drawLegend(kept);
    drawMap(mappable);
    drawUnmapped(rest);
    drawTable(kept);
  }

  if (D.csvUrl) {
    var host = document.getElementById('csvlink');
    host.appendChild(document.createTextNode('Filters above apply to this table. '));
    host.appendChild(anchor(D.csvUrl, 'Download the full CSV'));
  }

  buildFilters();
  buildHead();
  apply();
  fitMap();
})();
</script>
</body>
</html>
"""

TEMPLATE = TEMPLATE.replace("__GITHUB_MARK__", GITHUB_MARK)
