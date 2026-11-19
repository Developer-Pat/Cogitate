"""THE TRASH — one directory, one shelf per domain, one policy.

A deleted thing MOVES to `trash/<domain>/` rather than vanishing, and the trash
is a SURFACE: the page renders one tab per registered domain, the API answers
for any of them, and Exa reads the same endpoints the page does. Nothing may sit
in a holding area that no surface can see, which is the property the previous
shape (a row-driven "archived" list) could not offer.

THE PIECES:

    interface.py   the contract — what a domain IS (TrashEntry, TrashDomain)
    registry.py    the ONE map of shelves (key -> domain)
    services.py    the ONE policy layer (list, restore, purge, empty)
    listing.py     reading a shelf
    mechanics.py   removing — the containment-guarded, irreversible half
    adapters/      one file per domain: agents, test-runs, reports, dbs, misc

WHY THE SPLIT. The verbs are identical for every shelf, so they live in ONE
place (the service) and a shelf answers only what is ITS to answer: where it is,
what is on it, and how a thing is put back. A new shelf is a file plus one
registration — no page edit, no router edit, no second policy.
"""
