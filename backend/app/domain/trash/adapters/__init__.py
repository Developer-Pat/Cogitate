"""The trash's DOMAIN ADAPTERS — one shelf each.

An adapter answers the contract in `interface.py` for one directory: where it
is, what is on it, and how a thing on it is put back. The verbs' POLICY (which
shelf a caller means, the refusal to restore where there is no record) is the
service's, so the shelves stay comparable and a new shelf is a file plus a
registration.

The shelves:

    runs.py      retired test-run folders — RETAINS its own mechanics in
                 `app.domain.testing.trash`, which this adapter wraps
    reports.py   retired report areas — no record of origin, so purge only
    dbs.py       retired database backups — purge only
    misc.py      the fallback shelf: loose files and unclaimed directories,
                 so nothing in the trash root is invisible
    agents.py    trashed agent workspaces + residue (the lifecycle's shelf)
"""
