"""Adversarial tier (HIDDEN). Denominator = 11. Feeds COR/ROB; never the gate."""

import time

import csvparse
import pytest


def test_adv_unterminated_quote_mid_document():
    with pytest.raises(ValueError):
        csvparse.parse_csv('a,b\nc,"d,e\nf,g')


def test_adv_unterminated_quote_at_end():
    with pytest.raises(ValueError):
        csvparse.parse_csv('a,"bcd')


def test_adv_chars_after_closing_quote():
    # Sibling of the unterminated-quote construct; must share the same
    # raise/recover policy (REQUIREMENTS §1.6a).
    with pytest.raises(ValueError):
        csvparse.parse_csv('"ab"cd')


def test_adv_lone_quotechar_field():
    with pytest.raises(ValueError):
        csvparse.parse_csv('"')


def test_adv_mixed_crlf_lf_embedded_newlines():
    text = 'a,"embedded\r\nCRLF",b\nc,"embedded\nLF",d\r\n'
    result = csvparse.parse_csv(text)
    assert result == [["a", "embedded\r\nCRLF", "b"], ["c", "embedded\nLF", "d"]]


def test_adv_delimiter_and_newline_in_quotes():
    text = 'x,"a,b\nc,d",y'
    assert csvparse.parse_csv(text) == [["x", "a,b\nc,d", "y"]]


def test_adv_large_field_1mb():
    big = "x" * (1024 * 1024)
    text = f'a,"{big}",b'
    t0 = time.perf_counter()
    result = csvparse.parse_csv(text)
    elapsed = time.perf_counter() - t0
    assert result == [["a", big, "b"]]
    assert elapsed < 5.0


def test_adv_bom_with_quoted_first_field():
    text = '\ufeff"a,b",c'
    result = csvparse.parse_csv(text)
    assert result == [["a,b", "c"]]


def test_adv_whitespace_padded_unquoted_fields():
    # Whichever §1.6(b) policy: applied uniformly to leading/interior/trailing.
    r1 = csvparse.parse_csv(" a , b , c ")
    r2 = csvparse.parse_csv("  x  ,  y  ")
    assert len(r1[0]) == 3
    assert len(r2[0]) == 2
    stripped = all(f == f.strip() for f in r1[0])
    verbatim = r1[0] == [" a ", " b ", " c "]
    assert stripped or verbatim  # internally consistent with whichever policy
    if stripped:
        assert all(f == f.strip() for f in r2[0])
    else:
        assert r2[0] == ["  x  ", "  y  "]


def test_adv_crlf_only_document():
    assert csvparse.parse_csv("\r\n") == [[""]]


def test_adv_last_line_unterminated_quote():
    with pytest.raises(ValueError):
        csvparse.parse_csv('a,b\nc,d\n"')
