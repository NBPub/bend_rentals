# [Bend Rentals](https://nbpub.github.io/bend_rentals/)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/requests-HTTP-2C3E50)
![BeautifulSoup](https://img.shields.io/badge/Beautiful_Soup-HTML-71A5D8)
![pytest](https://img.shields.io/badge/pytest-offline-0A9EDC?logo=pytest&logoColor=white)
![Leaflet](https://img.shields.io/badge/Leaflet-map-199900?logo=leaflet&logoColor=white)
![Actions](https://img.shields.io/badge/GitHub_Actions-daily-2088FF?logo=githubactions&logoColor=white)
![Pages](https://img.shields.io/badge/GitHub_Pages-live-222222?logo=githubpages&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

[![Nominatim](https://img.shields.io/badge/Geocoding-Nominatim-7EBC6F?logo=openstreetmap&logoColor=white)](https://nominatim.openstreetmap.org/)
[![Census](https://img.shields.io/badge/Geocoding-US_Census-112E51)](https://geocoding.geo.census.gov/geocoder/)

A map and a searchable table of long-term rentals in Bend, Oregon, collected
once a day from the sites of sixteen local property management companies.

> **Not affiliated with any company listed here.** Every listing belongs to the
> site it was published on and links back to it. This is a directory, nothing
> more.
>
> **The data is presented as published.** It is read from each company's own
> page, and it is not cleaned or validated. Open the listing itself before
> acting on any of it. [More on that](DETAILS.md#data).

**[Project Details documentation](DETAILS.md#bend-rentals---details)**

**Contents**

| [Rental Listing Sources](#companies) | [AI disclaimer](#ai-disclaimer) | [Contributing](CONTRIBUTING.md#contributing) |

*[MIT Licensed](LICENSE)*

## Companies

Sixteen companies, five parsers. What gets read is usually not the company's
own website but the platform underneath it, because most of these render their
listings with JavaScript and serve HTML containing none of them. The registry
is [`sites.toml`](sites.toml); which domain each source is actually read from,
and how it was found, is in
[Details: Sources](DETAILS.md#sources).

| Company | Full name | Platform | Notes |
|---|---|---|---|
| [Velocity](https://velocitypropertymanagement.com/rentals) | Velocity Property Management | AppFolio | Their page is an iframe around the portal |
| [High Desert](https://www.highdesertpm.com/listings?city=Bend) | High Desert Property Management | AppFolio | Hundreds of listings statewide without the city filter |
| [Bend PM](https://www.bendpropertymanagement.com/vacancies) | Bend Property Management | AppFolio | Bend and Redmond |
| [Utopia](https://utopiamanagement.com/rental-list/bend-redmond-or) | Utopia Management | AppFolio | National: thousands of listings across dozens of states |
| [Elevation](https://www.epmbend.com/vacancies) | Elevation Property Management | AppFolio | Bend only |
| [Mountain View](https://www.today4rent.com/vacancies) | Mountain View Property Management | AppFolio | Bend and Redmond |
| [Superior](https://www.rentaroundbend.com/vacancies) | A Superior Property Management | AppFolio | Bend and Prineville |
| [High Country](https://www.hicountrypm.com/available-rentals-in-central-oregon) | High Country Property Management | AppFolio | Bend only |
| [Plus](https://investoregon.com/bend/) | Plus Property Management | AppFolio | Their own page omits the pet policies the portal carries |
| [Mt. Bachelor](https://www.bendpropertymanagement.net/bend-oregon-rentals) | Mt. Bachelor Property Management | AppFolio | States a pet policy on every listing, and refuses cats on all of them |
| [Lifestyles](https://www.bendlifestylesrentals.com/) | Lifestyles Realty Group | AppFolio | Bend, Redmond and Sunriver |
| [Trailhead](https://www.trailheadpropertymanagement.com/portfolio-1) | Trailhead Property Management | Squarespace | The only source whose listing *title* carries the data |
| [Hummingbird](https://hummingbirdpropertymanagement.managebuilding.com/Resident/public/rentals) | Hummingbird Property Management | Buildium | Pet policies appear only on the detail pages |
| [Preferred Residential](https://prbend.com/bend-long-term-rentals/) | Preferred Residential | WordPress | Publishes no street address. The only source stating a property type |
| [Ridgeline](https://ridgelinepropertymanagement.com/vacancies/) | Ridgeline Property Management | Rentvine | Publishes cat and dog booleans, and real coordinates |
| [PMI](https://www.bendpropertymanagementinc.com/bend-homes-for-rent) | PMI Central Oregon | Rentvine | Bend, Prineville, Madras and Hubbard |

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
