"""Smoke tier (VISIBLE to the strategy). Not weight-bearing; a fast self-check.

Verbatim from REQUIREMENTS.md §6.1 — chosen to demonstrate the constructs
without revealing the §1.6 answers.
"""

import csvparse


def test_smoke_simple_row():
    assert csvparse.parse_csv("a,b,c\n1,2,3\n") == [["a", "b", "c"], ["1", "2", "3"]]


def test_smoke_embedded_comma():
    assert csvparse.parse_csv('a,"b,c",d') == [["a", "b,c", "d"]]


def test_smoke_escaped_quote():
    assert csvparse.parse_csv('"say ""hi"""') == [['say "hi"']]


def test_smoke_embedded_newline_and_empty_fields():
    assert csvparse.parse_csv('x,"l1\nl2",y\r\nz,,\r\n') == [
        ["x", "l1\nl2", "y"],
        ["z", "", ""],
    ]


def test_smoke_custom_delimiter():
    assert csvparse.parse_csv("a;b", delimiter=";") == [["a", "b"]]
