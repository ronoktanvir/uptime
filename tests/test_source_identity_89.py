"""D03 option A: bounded exact source identity (source-identity/1).

Accepted values pass through byte-identically; everything else is refused with a
stable code. Every legacy restricted wire identifier is accepted unchanged, so
stored keys, hashes and signatures keep their exact bytes.
"""
import unicodedata

from hypothesis import given, settings, strategies as st
import pytest
from pydantic import TypeAdapter, ValidationError

from uptime import claim_identity
from uptime.source_identity import MAX_LENGTH, PUNCTUATION, SourceIdentity, VERSION, refusal, source_identity

ADAPTER = TypeAdapter(SourceIdentity)
LEGACY_ID = r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}"


def test_rule_is_versioned():
    assert VERSION == "source-identity/1" and MAX_LENGTH == 96 and PUNCTUATION == frozenset(".,'&()+:/_-")


@settings(max_examples=400, deadline=None)
@given(st.from_regex(LEGACY_ID, fullmatch=True))
def test_every_legacy_restricted_identifier_is_accepted_byte_identically(value):
    assert refusal(value) is None
    accepted = ADAPTER.validate_python(value)
    assert accepted == value and accepted.encode() == value.encode()


@pytest.mark.parametrize("value", [
    "harborline-001", "Cedar Orrery Studio", "Talus Signal Availability Agreement", "Acme, Inc.",
    "O'Neil & Sons (US)", "Plan+Plus", "acct:42/eu", "Café Nord", "東京 Analytics", "Harbor Fern Resource SLA",
    "x", "7", "a" * 96,
])
def test_bounded_source_values_pass_through_unchanged(value):
    assert ADAPTER.validate_python(value) == value
    assert source_identity(value) is value
    claim_identity._identity(value)  # the economic key rule accepts every bounded identity


@pytest.mark.parametrize("value,code", [
    ("", "empty"), ("a" * 97, "too_long"), ("Café Nord", "not_nfc"),
    ("Harborline ", "surrounding_space"), (" Harborline", "surrounding_space"),
    ("Harborline  Analytics", "repeated_space"), ("Tab\tName", "control_or_format"),
    ("Line\nBreak", "control_or_format"), ("Zero​Width", "control_or_format"), ("Joined‍Name", "control_or_format"),
    ("No Break", "whitespace"), ("Em Space", "whitespace"), ("Agreement — 2026", "character"),
    ("Acme #4", "character"), ("Acme; Ltd", "character"), ("Acme™", "character"), ("\U0001F600", "character"),
    ("()", "no_letter_or_digit"), ("...", "no_letter_or_digit"), (None, "not_text"), (42, "not_text"),
])
def test_values_outside_the_domain_are_refused_never_rewritten(value, code):
    assert refusal(value) == code
    with pytest.raises((ValidationError, ValueError)):
        ADAPTER.validate_python(value)


@settings(max_examples=400, deadline=None)
@given(st.text(min_size=0, max_size=110))
def test_acceptance_is_exactly_the_documented_predicate(value):
    expected = (0 < len(value) <= MAX_LENGTH and unicodedata.normalize("NFC", value) == value
                and value[:1] != " " and value[-1:] != " " and "  " not in value
                and all(c == " " or c in PUNCTUATION or unicodedata.category(c)[0] == "L"
                        or unicodedata.category(c) == "Nd" for c in value)
                and any(unicodedata.category(c)[0] == "L" or unicodedata.category(c) == "Nd" for c in value))
    assert (refusal(value) is None) == expected
    if expected:
        assert ADAPTER.validate_python(value) == value
        claim_identity._identity(value)
