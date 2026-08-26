# Lane implement_roman_module

## Outcome

Create the file `scenarios/L0-roman-numerals/solution/roman.py` implementing two pure functions:

- `to_roman(n: int) -> str` — converts an integer in `[1, 3999]` to its standard Roman numeral string using subtractive notation (e.g. 4→`IV`, 9→`IX`, 40→`XL`, 90→`XC`, 400→`CD`, 900→`CM`). Raises `ValueError` for values outside `[1, 3999]` or non-integer input.
- `from_roman(s: str) -> int` — converts a valid standard Roman numeral string to its integer value. Raises `ValueError` for empty, malformed, or non-standard numerals (e.g. `IIII`, `IC`, `VV`). Accepts uppercase only (reject lowercase with `ValueError`); document this policy in the docstring.

Both functions must be pure (no I/O, no globals, no side effects), use only the Python standard library, and target Python ≥ 3.11.

The solution directory must also contain an `__init__.py` (may be empty) if needed for the import to work, but the harness imports `roman` directly from `SOLUTION_DIR` on `sys.path`, so `solution/roman.py` is the primary deliverable.

## Steps

1. Create the directory `scenarios/L0-roman-numerals/solution/` if it does not exist.
2. Write `scenarios/L0-roman-numerals/solution/roman.py` with:
   - A module-level docstring.
   - `to_roman(n: int) -> str`:
     - Validate: raise `ValueError` if `not isinstance(n, int)` or `isinstance(n, bool)` or `n < 1` or `n > 3999`.
     - Use a lookup table of `(value, symbol)` pairs in descending order including all subtractive forms: `(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),(50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")`.
     - Build the result by repeatedly subtracting the largest fitting value and appending its symbol.
     - Docstring stating the contract and that `ValueError` is raised for out-of-range or non-integer input.
   - `from_roman(s: str) -> int`:
     - Validate: raise `ValueError` if `s` is empty or not a string.
     - Policy: accept uppercase only — raise `ValueError` if any character is lowercase.
     - Parse left-to-right using the standard subtractive rule (if current symbol value < next symbol value, subtract; otherwise add).
     - After computing the integer, round-trip validate: call `to_roman(result)` and compare to `s`; if they differ, raise `ValueError` (catches non-standard forms like `IIII`, `IC`, `VV`, `XM`).
     - Docstring stating the contract, the uppercase-only policy, and that `ValueError` is raised for invalid/non-standard input.
3. The `tests/conftest.py` sets `sys.path` to include `SOLUTION_DIR` (defaulting to `reference/solution` when `SOLUTION_DIR` is unset). To run the acceptance tests against the new solution, set `SOLUTION_DIR` to the absolute path of `scenarios/L0-roman-numerals/solution/` before invoking pytest, or rely on the harness to do so.

## Done when

The following command exits 0:

```
SOLUTION_DIR=$(pwd)/scenarios/L0-roman-numerals/solution pytest scenarios/L0-roman-numerals/tests/acceptance -q --tb=short
```

All 6 acceptance tests pass:
- `test_round_trip_sweep` — `from_roman(to_roman(n)) == n` for all n in [1, 3999]
- `test_subtractive_forms` — correct subtractive symbols
- `test_known_values` — spot-check known conversions
- `test_to_roman_invalid_raises` — ValueError for 0, 4000, -1, 3.5, "x"
- `test_from_roman_invalid_raises` — ValueError for "", "IIII", "IC", "VV", "ABC", "XM"
- `test_case_policy_consistent` — consistent case policy

The verifier command used by the orchestrator is:
```
pytest scenarios/L0-roman-numerals/tests/acceptance -q --tb=short
```
(run from the repo root with `SOLUTION_DIR` set by the harness environment).

## Final step (REQUIRED)

After the implementation is complete and the acceptance tests pass, write the file `artifacts/implement_roman_module.done` containing exactly the text `implement_roman_module:ok` and nothing else (no trailing newline beyond what is standard). This marker file is how the batch orchestrator confirms the lane finished — it must be the LAST action taken.
