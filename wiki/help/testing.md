---
title: Testing
category: testing
subtopic: Overview
order: 1
confidence: high
created: 2026-09-20
tags: [domain/help]
---

# Testing

Run the project's own tests, read what they protect, and see what the last runs
actually said. Every number on this page comes from a file the test runner
wrote — nothing here is estimated, simulated or animated.

## The tabs

**Runnable / Conditional / Quarantine** — the catalog: one row per test FILE.
Runnable needs nothing external; Conditional names the service it needs (and
SKIPS visibly with that reason when it is missing); Quarantine is parked, kept
visible rather than deleted. Every row carries its tier — `short` needs nothing
but the code, `medium` touches the database or the filesystem, `variable` is
anything that waits on a service or a LLM.

**Self-test** — the page's own check: deliberately failing tests, so a failure, a
skip and a cancel can be seen working. **It is meant to come out red**, and the tab
says what a correct run of it looks like — a red Self-test tab is the feature
working, not the suite broken.

**Runs** — the runs on disk, newest first, with what each one said (counts, the
FAILED list, and every skip WITH ITS REASON). A run of the page's own check is
marked **self-test**, so a deliberately red run cannot be mistaken for the suite
failing.

**Live** — the run in progress: what it has done so far, what it found, and the
per-test lines as they arrive.

## Running tests

**Run** starts the same test runner a terminal does, under the same lock. There
is no second runner and no job queue: what you see is one process.

- **What it runs:** the rows you have TICKED; with nothing ticked, everything the
  current tab and profile are showing. The control names the count either way.
- **The Profile list** narrows the view before you run: *Fast only* (no I/O — the
  quickest signal, and the default), *Everything*, *Needs the installation*
  (database, filesystem, the app itself).
- **A single row's Run** runs just that file.
- **One run at a time.** While a run holds the lock, **Run is disabled and says
  who holds it** — start a second and pytest's two runs present as *flaky tests*,
  blaming the code for a collision. A run started in a terminal, or by the system
  sweep, is picked up here automatically and shown live.

## Watching a run

The Live tab shows counts against **pytest's own collected total** ("312 of
1,190"), never a percentage and never an estimate: a bar over an unknown duration
would be a guess dressed as a measurement. The counts are marked as the live
count while the run goes, and switch to pytest's own final tally at the end.

The line-by-line feed is capped in view and says how many lines it is not
showing — the run keeps every one of them in its own events file. A test that
FAILS or SKIPS is shown with the reason, because that is the part you can act on.

**A run started outside this page is watch-only**, and says so: stopping someone
else's run is a deliberate act, not the side effect of a button, so **Cancel**
appears for a run this page started and not for one it did not.

**Cancel** stops the whole process group and then checks: it reports the lock as
released and names any process still alive. Killing only the first process would
leave workers behind holding the database — which is exactly the flakiness the
lock exists to prevent.

**How a run ended is stated in words**, not as an exit code: *all clear*,
*1 failed, 1 error*, *stopped — cancelled*, or *did not run* with the reason
(another run was already going, or the request matched nothing). The raw exit code
is on the tooltip for anyone who wants it; most people want to know whether
anything failed.

**Clear result** removes a finished run's result from the Live tab and the page,
for a clean look before the next one. It clears the VIEW only — the run stays in
Runs, and Delete (or a retire) is what removes it. A message confirms that when you
use it.

## Deleting a run, and the trash

**Delete** (on a run in the Runs tab) **moves the run's folder to the trash**
rather than erasing it, and says where it went — `trash/test-runs/<name>`, with
its `report.md`, `report.xml` and `events.jsonl` intact, so it can be recovered.
Nothing is pruned automatically: there is no retention rule anywhere on this page,
and **a run in progress cannot be deleted** while it is writing.

**Retiring several at once.** Tick runs in the Runs tab and **Retire selected**
moves them together. Two quick-selects only TICK — *Select self-test runs* and
*Select runs that did not pass* — so you still see the list, and still press the
one button that moves anything. The confirmation names every run first. The batch
answers for each one: **Moved**, **Refused** (a run in progress, with the lock's
own sentence) or **Not found**, all listed by name — a batch that said "done" while
one of nine was refused would be worse than no answer at all.

**Where they go.** Retiring a run moves its folder into the trash, and the
**Trash** button on the Runs tab opens the page that holds it (`/trash`, on the
Test runs shelf). That page is one surface over every shelf: it lists what is
there, puts an entry back with **Restore**, and removes one for good with
**Delete forever**. Nothing is pruned automatically, and a run in progress cannot
be retired while it is writing.

## Saving a run

**Save** (on a run in the Runs tab) keeps a **copy** of that run, so you have it
whether or not this page is around later. It asks where to put it the first time
and remembers the answer, and it names the exact path when it is done. Two things
it will not do: save a run that is being written (the files are mid-write), and
overwrite a copy that is already there — a second save of the same run is refused,
by name, with the path of the copy in the way.

The run stays in Runs either way: this is a copy, and nothing here is a repository
— nothing is saved unless you press Save, and nothing reads the copies back.

## Why a run failed — and what changed

Opening a run's detail shows its failures, its skips **with their reasons**, and
then **what changed**: the comparison against the last time that same selection ran
green. The lists are *newly failing* (passed there, fails here), *fixed*, *added*
and *gone* — and the page names the run it compared against, so the claim is
checkable.

**"The same selection" is a fact, not an assumption.** Every run records a
fingerprint of what it selected, so a run of a different set of files is never used
as a baseline. When there is nothing comparable — the first run of a selection, or
every earlier one failed — the page says exactly that instead of showing an empty
comparison, which would read as "nothing changed".

One run is one folder under `data/test-runs/<name>/`: `report.md` (the full
console record), `report.xml` (JUnit — per-test outcomes and skip messages), and
`events.jsonl` (one JSON line per thing that happened, as it happened).
