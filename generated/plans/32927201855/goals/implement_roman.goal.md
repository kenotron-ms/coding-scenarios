# Lane implement_roman

## Outcome

Create the file `scenarios/L0-roman-numerals/solution/roman.py` implementing two pure functions:

- `to_roman(n: int) -> str` — converts an integer in `[1, 3999]` to its standard Roman numeral string using subtractive notation.
- `from_roman(s: str) -> int` — converts a valid standard Roman numeral string to its integer value.

The module must live at `scenarios/L0-roman-numerals/solution/roman.py` (the `solution/` directory is the agent's workspace, and `roman` must be importable from there).

## Steps

1. Create the directory `scenarios/L0-roman-numerals/solution/` if it does not exist.

2. Create `scenarios/L0-roman-numerals/solution/roman.py` with the following implementation:

   **`to_roman(n: int) -> str`**
   - Raise `ValueError` if `n` is not an `int` instance (reject floats, strings, etc.) or if `n` is outside `[1, 3999]`.
   - Use a descending lookup table of `(value, symbol)` pairs covering all additive and subtractive forms:
     `(1000,"M"), (900,"CM"), (500,"D"), (400,"CD"), (100,"C"), (90,"XC"), (50,"L"), (40,"XL"), (10,"X"), (9,"IX"), (5,"V"), (4,"IV"), (1,"I")`
   - Build the result by repeatedly subtracting the largest fitting value.
   - Include a docstring stating the contract and that `ValueError` is raised for out-of-range or non-integer input.

   **`from_roman(s: str) -> int`**
   - Accept uppercase input only; raise `ValueError` for lowercase or mixed-case input (document this policy in the docstring).
   - Raise `ValueError` for empty string.
   - Parse left-to-right: if the current symbol's value is less than the next symbol's value, subtract it; otherwise add it.
   - After computing the candidate integer, validate by round-tripping: call `to_roman(result)` and confirm it equals `s`. If not, raise `ValueError` (this rejects non-canonical forms like `IIII`, `IC`, `VV`, `XM`, `VX`, etc.).
   - Raise `ValueError` for any string containing characters not in the Roman numeral alphabet `{I, V, X, L, C, D, M}`.
   - Include a docstring stating the contract, the case-sensitivity policy (uppercase only), and that `ValueError` is raised for invalid input.

3. Ensure the module passes `ruff` and `pyright` clean (use standard type annotations, no unused imports).

4. Verify the solution by running:
   ```
   SOLUTION_DIR=scenarios/L0-roman-numerals/solution pytest scenarios/L0-roman-numerals/tests/acceptance -q
   ```
   All 6 tests must pass.

## Done when

The command:
```
pytest scenarios/L0-roman-numerals/tests/acceptance -q
```
exits with code 0 (all acceptance tests pass). The `conftest.py` falls back to the `reference/solution` when `SOLUTION_DIR` is not set, so to test the actual solution run with `SOLUTION_DIR=scenarios/L0-roman-numerals/solution` set, **or** ensure the verifier is run from a context where `SOLUTION_DIR` points to `scenarios/L0-roman-numerals/solution`.

The verifier_argv for this lane is:
```
pytest scenarios/L0-roman-numerals/tests/acceptance -q
```
which must exit 0.

## Final step (REQUIRED)

After the work is done and the acceptance tests pass, write the file `artifacts/implement_roman.done` containing exactly the text `implement_roman:ok` and nothing else. This marker file is how the batch orchestrator confirms the lane finished — it must be the LAST action taken.
