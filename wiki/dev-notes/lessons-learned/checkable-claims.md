---
title: Checkable Claims
type: atlas-devnote
category: lessons-learned
order: 9
confidence: high
updated: 2026-09-17
tags: [type/dev-notes, domain/lessons]
---

# Checkable Claims

## The rules

1. **A comment asserting behaviour gets a test, or it gets deleted.** A claim
   that nothing checks drifts away from the code and then contradicts it.
2. **A guard must be able to catch what it claims to catch.** An `except` clause
   whose exception type can never be raised by the guarded block is decoration —
   and it hides the failure rather than reporting it. Check the MRO when the
   guarded code can raise something outside the hierarchy you assumed.
3. **A metric's name states its unit, and something asserts it is non-zero on a
   real path.** A field populated only with default values looks like data.
4. **A monitor must be shown the list of things it claims to cover.** A monitor
   that cannot see the file that breaks reports calm — which is worse than
   admitting it cannot see.
5. **A capability that nothing calls is not a capability.** Machinery that exists
   and is never wired looks finished and is inert; a reader finds the endpoint
   and assumes the feature.
6. **Say which state a defect is in — live or latent.** A field nothing reads
   today is a loaded gun, not a non-issue, and it should be labelled as such
   rather than filed as harmless.
7. **Before saying a finding out loud, name the one cheap check that would
   disprove it, and run it.** The failure mode this prevents is the strongest
   one here: a number is noticed, it fits the story already in hand, and the
   check that would falsify it is skipped because the story feels right.

8. **To measure a process's progress, measure something that is not buffered.**
   A file's byte count under a buffering writer grows in chunks: a 15-second
   window can show nothing at all while the process works normally. Sample the
   elapsed time against the reported percentage, or the work-completed list —
   never a buffered stream's size. A measurement that thins out, aggregates, or
   delays does not observe the same thing as a measurement that reads it
   directly.
9. **A timeout is not evidence of a hang.** If the cap sits below the real
   runtime, every run looks like a hang. Establish the expected duration before
   concluding anything from a timeout.
10. **A check is only as good as the numbers fed into it — derive them, do not
    assume them.** A measurement given an estimated input reports on the
    estimate, not on the system. A tooltip clip test assumed a 140px tip width
    and declared the tip cut; rendering the same string to measure it gave
    100px, which fitted comfortably. The identical test then cleared a 307px tip
    that *would* have been cut at the same boundary. **Both verdicts were wrong,
    in opposite directions, from one guessed number** — and the guess is
    invisible in the result, which reads as a clean measurement either way.

## Why it matters

Every rule above describes the same defect shape: a thing that reads as if it
does something, and does not. This class is invisible to the way we normally
review — by reading. It cannot be caught by reading a diff, because it *looks*
correct; it is only caught by the MRO, a query, the file list, or a run.

That is why these recur. A visibly broken thing is fixed the same day; a claim
that merely looks true survives for weeks and quietly corrupts the surfaces
people use to find out what is really happening.

## Related

- [[dev-notes/configuration/policies|Configuration Policies]]
- [[dev-notes/known-issues|Known Issues]]
- [[dev-notes/lessons-learned/verify-before-removing|Verify Before Removing]]
