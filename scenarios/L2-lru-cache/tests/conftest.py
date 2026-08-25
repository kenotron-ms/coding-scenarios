"""Puts the solution-under-test on sys.path via SOLUTION_DIR (set by the harness).

Falls back to the reference solution so the suites are runnable directly with
`pytest` during grader development.

Also provides `FakeClock`, the deterministic clock injected by every
acceptance/adversarial test (GRADING.md §8: acceptance/adversarial suites
control time; no `time.sleep`, no wall-clock flakiness). This module's
directory is placed on `sys.path` by pytest's rootless import of this
conftest, so `from conftest import FakeClock` works from any test file under
`tests/`.
"""

import os
import sys
from pathlib import Path
from typing import ClassVar

_sol = os.environ.get("SOLUTION_DIR")
if not _sol:
    _sol = str(Path(__file__).resolve().parent.parent / "reference" / "solution")
if _sol not in sys.path:
    sys.path.insert(0, _sol)


class FakeClock:
    """Deterministic, controllable stand-in for `time.monotonic`.

    Calling the instance (`clock()`) returns the current simulated time;
    `.advance(dt)` moves it forward by `dt` seconds (`dt >= 0`). Never moves
    backwards, matching the "clock is assumed non-decreasing" contract
    (REQUIREMENTS FR-11).
    """

    def __init__(self, start: float = 0.0) -> None:
        self._t = float(start)

    def __call__(self) -> float:
        return self._t

    def advance(self, dt: float) -> None:
        if dt < 0:
            raise ValueError(f"FakeClock.advance: dt must be >= 0, got {dt!r}")
        self._t += dt


class CountingKey:
    """A key wrapper that tallies its own `__hash__`/`__eq__` calls.

    Used by the NFR-1 complexity probe: per-op comparison counts must stay
    flat across `capacity` (an O(n) victim scan would show counts growing
    with capacity; an O(1) recency structure will not).
    """

    calls: ClassVar[dict[str, int]] = {"hash": 0, "eq": 0}

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        CountingKey.calls["hash"] += 1
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        CountingKey.calls["eq"] += 1
        return isinstance(other, CountingKey) and self.value == other.value

    @classmethod
    def reset(cls) -> None:
        cls.calls = {"hash": 0, "eq": 0}

    @classmethod
    def total(cls) -> int:
        return cls.calls["hash"] + cls.calls["eq"]
