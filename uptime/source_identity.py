"""Bounded exact source identity — team decision D03, option A (confirmed 2026-11-09).

An account or agreement identity is the exact text its source uses. It is
accepted only when it already lies inside one bounded domain, and is otherwise
refused. Nothing here trims, folds case, normalizes Unicode, slugs or maps a
value: a caller that receives a refusal must obtain the exact source value.

Domain ``source-identity/1``: 1–96 characters; Unicode letters, decimal digits,
single ASCII spaces and ``. , ' & ( ) + : / _ -``; at least one letter or digit;
no leading, trailing or repeated space; already in NFC. The restricted legacy
wire identifier ``^[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}$`` is a strict subset, so
stored legacy identities, keys, hashes and signatures keep their exact bytes.

Technical route, artifact and evidence-reference identifiers keep their own
restricted types; this module is only for identity-bearing source names.
"""
from typing import Annotated
import unicodedata

from pydantic import AfterValidator

VERSION = "source-identity/1"
MAX_LENGTH = 96
PUNCTUATION = frozenset(".,'&()+:/_-")


def refusal(value):
    """Return a stable refusal code, or None when ``value`` is a valid identity."""
    if not isinstance(value, str):
        return "not_text"
    if not value:
        return "empty"
    if len(value) > MAX_LENGTH:
        return "too_long"
    if unicodedata.normalize("NFC", value) != value:
        return "not_nfc"
    if value[0] == " " or value[-1] == " ":
        return "surrounding_space"
    meaningful = False
    for character in value:
        category = unicodedata.category(character)
        if category.startswith("L") or category == "Nd":
            meaningful = True
        elif character != " " and character not in PUNCTUATION:
            if category.startswith("C"):
                return "control_or_format"
            return "whitespace" if character.isspace() else "character"
    if "  " in value:
        return "repeated_space"
    if not meaningful:
        return "no_letter_or_digit"
    return None


def source_identity(value):
    reason = refusal(value)
    if reason is not None:
        raise ValueError(f"A bounded exact source identity is required ({reason}); values are refused, never rewritten.")
    return value


SourceIdentity = Annotated[str, AfterValidator(source_identity)]
