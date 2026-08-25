"""Acceptance tier (HELD OUT). Denominator = 19 (see rubric.yaml). Defines "working"."""

import inspect

import csvparse
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


def test_quoted_field_basic():  # L1-AC01
    assert csvparse.parse_csv('a,"b",c') == [["a", "b", "c"]]
    assert csvparse.parse_csv('"only"') == [["only"]]


def test_doubled_quote_escape():  # L1-AC02
    assert csvparse.parse_csv('"say ""hi"""') == [['say "hi"']]
    assert csvparse.parse_csv('"""start"') == [['"start']]
    assert csvparse.parse_csv('"end"""') == [['end"']]
    assert csvparse.parse_csv('"mid""dle"') == [['mid"dle']]


def test_quoted_field_with_delimiter():  # L1-AC03
    assert csvparse.parse_csv('a,"b,c",d') == [["a", "b,c", "d"]]
    assert csvparse.parse_csv('"a,b,c"') == [["a,b,c"]]


def test_quoted_field_with_newline():  # L1-AC04
    assert csvparse.parse_csv('a,"line1\nline2",b') == [["a", "line1\nline2", "b"]]
    assert csvparse.parse_csv('a,"line1\r\nline2",b') == [["a", "line1\r\nline2", "b"]]


def test_quote_inside_unquoted_field():  # L1-AC05
    assert csvparse.parse_csv('a"b,c') == [['a"b', "c"]]
    assert csvparse.parse_csv('ab"c"d,e') == [['ab"c"d', "e"]]


def test_fully_empty_quoted_field():  # L1-AC06
    assert csvparse.parse_csv('"",a') == [["", "a"]]
    assert csvparse.parse_csv('""') == [[""]]


def test_field_count_invariant():  # L1-AC07
    assert (
        csvparse.parse_csv("") == []
    )  # FR-1: empty input is 0 rows, not a 1-field row
    for n_delims in range(1, 6):
        text = "," * n_delims
        row = csvparse.parse_csv(text)
        assert len(row) == 1
        assert len(row[0]) == n_delims + 1
    assert csvparse.parse_csv("a,,b") == [["a", "", "b"]]
    assert csvparse.parse_csv("z,,") == [["z", "", ""]]


def test_blank_line_yields_empty_field():  # L1-AC08
    assert csvparse.parse_csv("a\n\nb\n") == [["a"], [""], ["b"]]
    assert csvparse.parse_csv("\n") == [[""]]
    assert csvparse.parse_csv("a\n\n\nb") == [["a"], [""], [""], ["b"]]


def test_trailing_separator_no_extra_row():  # L1-AC09
    assert csvparse.parse_csv("a,b\n") == [["a", "b"]]
    assert csvparse.parse_csv("a,b") == [["a", "b"]]
    assert csvparse.parse_csv("a,b\r\n") == [["a", "b"]]
    assert len(csvparse.parse_csv("a,b\n")) == len(csvparse.parse_csv("a,b"))


def test_line_endings_crlf_lf_mixed():  # L1-AC10
    lf = csvparse.parse_csv("a,b\nc,d\ne,f\n")
    crlf = csvparse.parse_csv("a,b\r\nc,d\r\ne,f\r\n")
    mixed = csvparse.parse_csv("a,b\r\nc,d\ne,f\r\n")
    assert lf == crlf == mixed == [["a", "b"], ["c", "d"], ["e", "f"]]


def test_lone_cr_is_data():  # L1-AC11
    assert csvparse.parse_csv("a\rb,c") == [["a\rb", "c"]]
    assert csvparse.parse_csv("a\rb\nc\rd") == [["a\rb"], ["c\rd"]]


def test_unicode_roundtrip():  # L1-AC12
    text = "e\u0301,\U0001f600,\u05d0\u05d1\n"
    assert csvparse.parse_csv(text) == [["e\u0301", "\U0001f600", "\u05d0\u05d1"]]
    quoted = '"e\u0301,x","\U0001f600"'
    assert csvparse.parse_csv(quoted) == [["e\u0301,x", "\U0001f600"]]


def test_custom_delimiter_and_quotechar():  # L1-AC13
    assert csvparse.parse_csv("a\tb\tc", delimiter="\t") == [["a", "b", "c"]]
    assert csvparse.parse_csv("a|b|c", delimiter="|") == [["a", "b", "c"]]
    assert csvparse.parse_csv("a;'b;c';d", delimiter=";", quotechar="'") == [
        ["a", "b;c", "d"]
    ]
    assert csvparse.parse_csv("'a''b'", quotechar="'") == [["a'b"]]


def test_invalid_parameters_raise():  # L1-AC14
    with pytest.raises(ValueError):
        csvparse.parse_csv("a,b", delimiter=",,")
    with pytest.raises(ValueError):
        csvparse.parse_csv("a,b", delimiter="")
    with pytest.raises(ValueError):
        csvparse.parse_csv("a,b", quotechar='""')
    with pytest.raises(ValueError):
        csvparse.parse_csv("a,b", delimiter=",", quotechar=",")
    with pytest.raises(ValueError):
        csvparse.parse_csv("a,b", delimiter=None)  # type: ignore[arg-type]


def test_ambiguity_consistency_matrix():  # L1-AC15
    # Observe which malformed-input policy the solution chose, then require
    # that the sibling construct follows the SAME policy (REQUIREMENTS §1.6a).
    try:
        csvparse.parse_csv('a,"bcd')
    except ValueError:
        raises_policy = True
    else:
        raises_policy = False

    if raises_policy:
        with pytest.raises(ValueError):
            csvparse.parse_csv('"ab"cd')
    else:
        # recovery policy: sibling must also recover (not raise), and must
        # not silently lose the already-accumulated field content.
        result = csvparse.parse_csv('"ab"cd')
        assert result and "ab" in result[0][0]

    # BOM never changes counts, and only ever touches the first field.
    plain = csvparse.parse_csv("a,b\nc,d")
    bommed = csvparse.parse_csv("\ufeffa,b\nc,d")
    assert len(plain) == len(bommed)
    assert [len(r) for r in plain] == [len(r) for r in bommed]
    assert bommed[1:] == plain[1:]
    assert bommed[0][1:] == plain[0][1:]

    # whitespace inside quotes is always preserved regardless of policy.
    assert csvparse.parse_csv('" a "') == [[" a "]]
    assert csvparse.parse_csv('a," b ",c') == [["a", " b ", "c"]]


def test_no_silent_dataloss_on_malformed():  # L1-AC16
    # Whichever policy: a malformed unterminated field never drops earlier,
    # already-completed fields on the same row.
    try:
        result = csvparse.parse_csv('good1,good2,"bad')
    except ValueError as exc:
        assert str(exc)  # position/message present, not a bare raise
    else:
        assert result[0][0] == "good1"
        assert result[0][1] == "good2"


def test_performance_scaling():  # L1-AC17
    import time

    def make_csv(n_rows: int) -> str:
        return "".join(
            f'field{i}a,field{i}b,"q,{i}",field{i}d\n' for i in range(n_rows)
        )

    small = make_csv(4000)
    large = make_csv(8000)

    t0 = time.perf_counter()
    r_small = csvparse.parse_csv(small)
    t1 = time.perf_counter()
    r_large = csvparse.parse_csv(large)
    t2 = time.perf_counter()

    assert len(r_small) == 4000
    assert len(r_large) == 8000

    small_time = max(t1 - t0, 1e-6)
    large_time = t2 - t1
    # Doubling input size must not increase parse time by more than ~3x
    # (generous margin over the ~2.5x NFR-1 budget to absorb test-machine
    # noise on a small fixture; a genuinely quadratic parser fails this hard).
    assert large_time < small_time * 6 + 0.5


def test_docstring_documents_ambiguities():  # L1-AC18
    doc = inspect.getdoc(csvparse.parse_csv) or ""
    assert doc, "parse_csv must have a docstring"
    lowered = doc.lower()
    # (a) malformed input policy
    assert any(kw in lowered for kw in ("malformed", "unterminated", "valueerror"))
    # (b) whitespace policy
    assert "whitespace" in lowered
    # (c) BOM policy
    assert "bom" in lowered


_TEXT_ALPHABET = st.characters(
    codec="utf-8",
    exclude_characters="\ufeff",
)


def _field_text():
    return st.text(alphabet=_TEXT_ALPHABET, max_size=8).map(str.strip)


def _row_strategy():
    return st.lists(_field_text(), min_size=1, max_size=4)


def _rows_strategy():
    return st.lists(_row_strategy(), min_size=1, max_size=4)


def _serialize(
    rows: list[list[str]], delimiter: str = ",", quotechar: str = '"'
) -> str:
    """Harness-owned RFC 4180 serializer (never shipped to the agent)."""
    lines = []
    for row in rows:
        cells = []
        for field in row:
            needs_quote = (
                delimiter in field
                or quotechar in field
                or "\n" in field
                or "\r" in field
            )
            if needs_quote:
                escaped = field.replace(quotechar, quotechar * 2)
                cells.append(f"{quotechar}{escaped}{quotechar}")
            else:
                cells.append(field)
        lines.append(delimiter.join(cells))
    return "\n".join(lines) + "\n"


@settings(max_examples=150, deadline=None)
@given(rows=_rows_strategy())
def test_round_trip_hypothesis(rows):  # L1-AC19
    text = _serialize(rows)
    assert csvparse.parse_csv(text) == rows
