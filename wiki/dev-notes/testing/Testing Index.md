---
title: Dev Notes — Testing
type: atlas-index
path: wiki/dev-notes/testing
confidence: stub
updated: 2026-08-05
tags: [type/index, domain/testing]
---

# Testing — Dev Notes

The testing dev notes — testing and tool-testing practices.


## Inventory

- [[dev-notes/testing/README|Testing (the test suite)]] — **start here**: the
  two areas (test sweep vs system sweep), how to run the tests, the groups,
  the approximately-how-long, and why the sequential path is the slow one
- [[dev-notes/testing/testing|Testing & Tool Testing]]
- [[dev-notes/testing/test-isolation|Test Isolation]] — the suite runs in its
  own installation: one temp root, and why a settings-derived path must go
  through `Paths`
- [[dev-notes/testing/test-tiers|Test Tiers]] — partition by dependency, least
  first; the `backend` and `live` skip gates, and why a live probe must answer
  for the SPECIFIC service
