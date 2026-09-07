# data/

`listings.csv` lives here, and it is committed.

Everything else in this directory is ignored. The scheduled workflow rewrites
`listings.csv` once a day and commits it, so `git log -p -- data/listings.csv`
is the history of what changed.

`snapshots/` appears when you run `scrape.py` locally: one dated copy of the
CSV per run, which is what `changes.py` compares. It is gitignored, because on
the published repo git itself already holds that history. CI skips it with
`--no-snapshot`.
