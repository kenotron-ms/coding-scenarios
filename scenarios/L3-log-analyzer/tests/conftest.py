"""Test wiring for the L3 log-analyzer grader.

Puts the ``tests/`` directory on ``sys.path`` so every tier can ``import
_harness`` (the harness-owned helpers), and resolves the solution-under-test via
``SOLUTION_DIR`` (set by the harness), falling back to the reference solution so
the suites are runnable directly with ``pytest`` during grader development.

Unlike L0/L1/L2 (``kind: python-module``), L3 is ``kind: cli``: the suites never
import the solution -- they run the built CLI as a subprocess
(``python -m loganalyze``) from ``SOLUTION_DIR`` (REQUIREMENTS.md §2.5/§6.3).
"""

import os
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

os.environ.setdefault("SOLUTION_DIR", str(_TESTS.parent / "reference" / "solution"))
