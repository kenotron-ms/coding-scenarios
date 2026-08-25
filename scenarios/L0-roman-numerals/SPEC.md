# L0 — Roman Numerals — SPEC (prompt handed to the strategy under test)

Implement two pure functions in a single module `roman.py` in your workspace.

```python
def to_roman(n: int) -> str: ...
def from_roman(s: str) -> int: ...
```

Requirements:
- `to_roman(n)` returns the standard Roman numeral for integers `1 ≤ n ≤ 3999`
  using subtractive notation (4→`IV`, 9→`IX`, 40→`XL`, 90→`XC`, 400→`CD`, 900→`CM`).
- `from_roman(s)` returns the integer for a valid standard Roman numeral.
- Round-trip: `from_roman(to_roman(n)) == n` for all `n` in `[1, 3999]`.
- `to_roman` raises `ValueError` for out-of-range or non-integer input.
- `from_roman` raises `ValueError` for empty, malformed, or non-standard numerals
  (e.g., `IIII`, `IC`, `VV`).
- Standard library only. Pure functions (no I/O, no globals).
- Resolve and **document in the `from_roman` docstring** the case-sensitivity
  policy (accept uppercase only, or accept case-insensitively) — either is fine
  if applied consistently.

You are given `tests/smoke/` to check your work. Held-out acceptance and
adversarial suites will grade you (see `EVALUATION.md` for what they measure).

**Entrypoint:** the harness imports `roman` from your workspace (see `manifest.yaml`).
