# cache/

`geocode.json` lives here, and it is committed on purpose.

It maps a normalised street address to its coordinates. Rebuilding it means
re-asking Nominatim about every address, which their usage policy quite
reasonably asks us not to do, so the cache is permanent and a fresh clone
geocodes nothing. Coordinates for a street address do not change.

Addresses no provider could resolve are cached as failures too, so they are
never retried. A *network* error is not cached: it may be transient.
