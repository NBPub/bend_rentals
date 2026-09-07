# [Bend Rentals](https://nbpub.github.io/bend_rentals/)

A map and a searchable table of long-term rentals in Bend, Oregon, collected
once a day from the sites of thirteen local property management companies.

| [Rental Listing Sources](#companies) | [AI disclaimer](#ai-disclaimer) | [Contributing](CONTRIBUTING.md#contributing) |

**[Project Details documentation](DETAILS.md#bend-rentals---details)**

> Not affiliated with any of the companies listed here. Every listing belongs
> to the site it was published on, and links back to it. This is a directory
> that saves you opening thirteen tabs, not a broker.

*[MIT Licensed](LICENSE)*

## Companies

Each entry gives the company's own rentals page, how its listings are
published, and the domain the data is actually read from — which is often not
the same, because most of these sites render their listings with JavaScript
and serve HTML containing none of them.

**AppFolio** — nine of the thirteen. Every field is on the index card, so one
request covers the whole source. Their portals publish `Crawl-delay: 10`,
which is most of the time a full run takes.

- **Velocity** — [velocitypropertymanagement.com](https://velocitypropertymanagement.com/rentals)
  - The company page is an iframe wrapped around the portal below.
  - Read from `velocitypm.appfolio.com`
- **High Desert** — [highdesertpm.com](https://www.highdesertpm.com/listings?city=Bend)
  - A Next.js front end that renders nothing server-side.
  - Read from `highdesertpm.appfolio.com`
- **Bend PM** — [bendpropertymanagement.com](https://www.bendpropertymanagement.com/vacancies)
  - Lists Bend and Redmond, so the city filter is applied at the source.
  - Read from `bend.appfolio.com`
- **Utopia** — [utopiamanagement.com](https://utopiamanagement.com/rental-list/bend-redmond-or)
  - A national company: thousands of listings across dozens of states.
  - Read from `utopiamanagement.appfolio.com`
- **Elevation** — [epmbend.com](https://www.epmbend.com/vacancies)
  - A Squarespace shell; the portal was found through its tenant login link.
  - Read from `elevationpropmgmt.appfolio.com`
- **Mountain View** — [today4rent.com](https://www.today4rent.com/vacancies)
  - Duda-built, listings loaded client-side. Covers Bend and Redmond.
  - Read from `mountainviewpm.appfolio.com`
- **Superior** — [rentaroundbend.com](https://www.rentaroundbend.com/vacancies)
  - Duda-built. Covers Bend and Prineville.
  - Read from `asuperior.appfolio.com`
- **High Country** — [hicountrypm.com](https://www.hicountrypm.com/available-rentals-in-central-oregon)
  - Duda-built. Bend only.
  - Read from `highcountrypropmgmt.appfolio.com`
- **Plus** — [investoregon.com](https://investoregon.com/bend/)
  - A WordPress feed of the portal below, which carries pet policies the
    WordPress page leaves out. Covers Bend, Prineville and Redmond.
  - Read from `pluspmllc.appfolio.com`

**Everything else** — one source per platform.

- **Trailhead** — [trailheadpropertymanagement.com](https://www.trailheadpropertymanagement.com/portfolio-1)
  - Squarespace. The only source whose listing *title* carries the data —
    `$3,550 / 3br - 2472ft2 - Description (SW Bend)` — so it needs a page per
    listing and a title parser. Its second portfolio is vacation rentals and
    is deliberately left alone.
  - Read from the same domain
- **Hummingbird** — [hummingbirdpropertymanagement.managebuilding.com](https://hummingbirdpropertymanagement.managebuilding.com/Resident/public/rentals)
  - Buildium resident portal. The index cards carry no link to their own
    detail pages, so the parser collects the detail URLs and reads those —
    which also carry a pet policy the index omits.
  - Read from the same domain
- **Preferred Residential** — [prbend.com](https://prbend.com/bend-long-term-rentals/)
  - WordPress, with labelled fields on each property page. Publishes **no
    street address**: the only one on a page is the agency's own office, so
    the address and coordinates come from resolving the "View This Rental on
    a Map" link instead. The only source that states a property type.
  - Read from the same domain
- **Ridgeline** — [ridgelinepropertymanagement.com](https://ridgelinepropertymanagement.com/vacancies/)
  - Rentvine. The vacancies page is a JavaScript widget; what is read is the
    public JSON endpoint that widget itself calls. The richest source here:
    explicit cat and dog booleans, and real coordinates, so it needs no
    geocoding at all.
  - Read from `ridgelinepropertymgmt.rentvine.com`

Suggestions for sources to add are welcome — see
[Contributing](CONTRIBUTING.md#contributing). A link to a Bend property
manager's rentals page is enough to start with; working out how to read it is
the part that takes doing.

## AI disclaimer

Architecture, feature scope, source selection and the review loops were
human-planned and human-directed; an AI assistant did much of the
implementation and documentation drafting under that direction. The design and
judgement calls are the author's, the keystrokes largely the model's.

## Contributing

Issues and pull requests are welcome, particularly for a source that has
changed its markup. Suggestions of new sources are welcome too, and need no
code: a link to the company's rentals page is enough. See
[Contributing](CONTRIBUTING.md#contributing).
