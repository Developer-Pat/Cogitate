"""The page's own exercise — every outcome the page renders, on purpose.

**THIS SUITE IS DELIBERATELY RED.** A run of it produces one pass, one failure,
one skip with a reason, one setup error and one test slow enough to cancel, so
the user-testing page has real material for every column it draws instead of
being exercised only against whatever the suite happened to be doing that day.

**It is not in any group, and no sweep collects it.** It lives outside
`backend/tests/` on purpose: `testpaths` and the runner's own groups both select
`tests/`, so a red fixture sitting inside the tree would turn every full run and
every sweep red — and a suite that is always red tells you nothing. The page runs
it BY NAME, from its own tab.

`EXPECTED_SHAPE` below is the pass condition, and the page reads it from HERE
rather than carrying its own copy: a red Self-test tab must not read as a broken
app, and a number written in two places drifts in one of them.
"""

import time

import pytest

#: What a CORRECT run of this suite looks like. The page shows this sentence
#: verbatim beside the tab, so red here is expected rather than alarming.
EXPECTED_SHAPE = (
    "2 passed, 1 failed, 1 error, 1 skipped — one of them waits 25s, "
    "which is what Cancel needs to stop mid-flight"
)

#: Long enough to reach for Cancel, short enough to sit through when you do not.
SLOW_SECONDS = 25


def test_a_pass() -> None:
    """The green column: a test that does what it says."""
    assert 2 + 2 == 4


def test_a_failure() -> None:
    """The failure column: a real assertion failure, and it says what it is.

    The message matters — the page's FAILED list shows it, and a message that
    says only "assert 4 == 5" leaves the reader wondering whether the app is
    broken or the test is doing its job.
    """
    assert 2 + 2 == 5, "deliberate failure — this suite exists to be red"


def test_a_skip() -> None:
    """The skip column: a skip whose REASON has to survive the trip to the page."""
    pytest.skip("deliberate skip — the page must show this reason, not just a count")


@pytest.fixture
def an_impossible_setup() -> None:
    """Set up something that cannot be set up, which is an ERROR, not a failure."""
    raise RuntimeError("deliberate setup error — this test never reaches a verdict")


def test_an_error(an_impossible_setup: None) -> None:
    """The error column: a test that never reached a verdict, reported as an error."""
    assert True


def test_slow_enough_to_cancel() -> None:
    """The Cancel column: a run still going when you reach for the button.

    The wait is the whole point. A run that ends in a second cannot demonstrate
    a group kill, and the page's Cancel is verified — it names any survivor
    rather than claiming success.
    """
    time.sleep(SLOW_SECONDS)
    assert True
