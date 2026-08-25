"""Puts the solution-under-test on sys.path via SOLUTION_DIR (set by the harness).

Falls back to the reference solution so the suites are runnable directly with
`pytest` during grader development.
"""
import os
import sys
from pathlib import Path

_sol = os.environ.get("SOLUTION_DIR")
if not _sol:
    _sol = str(Path(__file__).resolve().parent.parent / "reference" / "solution")
if _sol not in sys.path:
    sys.path.insert(0, _sol)
