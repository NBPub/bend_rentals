# cache/

`geocode.json` lives here, and it is committed on purpose.

It maps a normalised street address to its coordinates. Rebuilding it means
re-asking Nominatim about every address, which their usage policy quite
reasonably asks us not to do, so a resolved address is kept for good and a
fresh clone geocodes nothing. Coordinates for a street address do not change.

A failure is kept too, but only for thirty days. It never meant more than
"no provider knows this address yet", and that is a statement about today:
OpenStreetMap gains streets constantly, so caching the verdict forever would
keep a newly mapped listing off the map permanently. A *network* error is not
cached at all, since it may be transient.
