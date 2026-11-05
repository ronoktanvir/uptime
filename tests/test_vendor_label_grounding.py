"""Stable label phrases share bounded whitespace handling without rewriting provenance."""
from hashlib import sha256

import pytest

from test_vendor_resource import compiled, extend_source

FIELDS = ("symptoms", "provider_causes", "exclusions", "fee_exclusions", "request_fields")
SPACES = (" ", "\n", "\r\n", "\r", "\t", "\u00a0", " \t\n\r\u00a0 ")
OTHER_SPACES = tuple(chr(n) for n in range(0x110000) if chr(n).isspace() and chr(n) not in " \t\n\r\u00a0")


def row(key, phrase, quote=None, label="source_descriptor"):
    return (quote or "The cited descriptor is " + phrase + ".",
            {key:[{"label":label,"phrase":phrase}]})


@pytest.mark.parametrize("key", FIELDS)
@pytest.mark.parametrize("space", SPACES)
def test_exact_and_normalized_phrases_preserve_original_source(key, space):
    original = "recorded service" + space + "condition"
    quote = "The cited descriptor is " + original + "."
    for phrase in (original, "recorded service condition"):
        document, proposal = extend_source([row(key, phrase, quote)])
        manifest = compiled(document, proposal)
        citation = manifest["citations"][-1]
        binding = manifest["label_bindings"][key]["source_descriptor"]
        assert binding == {"phrase":phrase,"block":citation["id"],"block_sha256":sha256(quote.encode()).hexdigest()}
        assert manifest[key].count("source_descriptor") == 1
        assert citation["quote"] == quote == document["text"][citation["start"]:citation["end"]]
        assert citation["block_sha256"] == sha256(quote.encode()).hexdigest()
        assert manifest["document"]["sha256"] == sha256(document["text"].encode()).hexdigest()


@pytest.mark.parametrize("key", FIELDS)
@pytest.mark.parametrize("space", OTHER_SPACES)
def test_exotic_phrase_whitespace_refuses_but_existing_source_normalization_remains(key, space):
    phrase = "recorded" + space + "condition"
    quote = "The cited descriptor is " + phrase + "."
    with pytest.raises(ValueError, match="Ungrounded"):
        compiled(*extend_source([row(key, phrase, "The cited descriptor is recorded condition.")]))
    if ord(space) < 32:
        with pytest.raises(ValueError, match="Unsupported document encoding"):
            compiled(*extend_source([row(key, "recorded condition", quote)]))
        return
    manifest = compiled(*extend_source([row(key, "recorded condition", quote)]))
    assert manifest["label_bindings"][key]["source_descriptor"]["phrase"] == "recorded condition"


@pytest.mark.parametrize("phrase", [
    "condition service recorded", "recorded severe service condition", "recordedservice condition",
    "recorded ser vice condition", "Recorded service condition", "recorded servicecondition",
    "recorded service\u200b condition", "recorded service\ufeff condition", "recorded service\u00ad condition",
    "recorded ser-\nvice condition", "recorded, service condition",
])
def test_whitespace_normalization_does_not_change_words_or_punctuation(phrase):
    with pytest.raises(ValueError, match="Ungrounded"):
        compiled(*extend_source([row("symptoms", phrase, "The cited descriptor is recorded service condition.")]))


@pytest.mark.parametrize(("phrase", "source"), [("caf\u00e9 failure", "cafe\u0301 failure"), ("cafe\u0301 failure", "caf\u00e9 failure")])
def test_unicode_composition_is_not_normalized(phrase, source):
    with pytest.raises(ValueError, match="Ungrounded"):
        compiled(*extend_source([row("symptoms", phrase, "The cited descriptor is " + source + ".")]))


@pytest.mark.parametrize("phrase", [" ", "\n", "\r", "\t", "\u00a0", "\u3000", " \t\r\n ", " " * 256 + "x"])
def test_phrase_bounds_apply_before_nonempty_normalization(phrase):
    with pytest.raises(ValueError, match="Ungrounded"):
        compiled(*extend_source([row("symptoms", phrase, "The cited descriptor is x.")]))


@pytest.mark.parametrize("label", ["Uppercase", "contains-hyphen", "a" * 65, ""])
def test_stable_identifier_bounds_are_unchanged(label):
    with pytest.raises(ValueError, match="Ungrounded"):
        compiled(*extend_source([row("symptoms", "recorded\ncondition", label=label)]))


def test_phrase_cannot_come_from_adjacent_block_or_cross_block_boundary():
    for phrase in ("recorded condition", "condition The cited descriptor"):
        with pytest.raises(ValueError, match="Ungrounded"):
            compiled(*extend_source([
                row("symptoms", "recorded condition", "The cited descriptor is recorded condition"),
                row("provider_causes", phrase, "The cited descriptor is a separate failure."),
            ]))


@pytest.mark.parametrize("same_block", [False, True])
def test_whitespace_different_definitions_keep_raw_collision_refusal(same_block):
    phrase, wrapped = "recorded condition", "recorded\ncondition"
    quote = "The cited descriptor is " + wrapped + "."
    rows = [row("symptoms", phrase, quote), row("symptoms", wrapped, quote)]
    if same_block:
        rows = [(quote, {"symptoms":[rows[0][1]["symptoms"][0], rows[1][1]["symptoms"][0]]})]
    with pytest.raises(ValueError, match="Conflicting definitions"):
        compiled(*extend_source(rows))


def test_identical_repeats_and_distinct_aliases_preserve_existing_behavior():
    quote = "The cited descriptor is recorded condition."
    values = {"symptoms":[{"label":label,"phrase":"recorded condition"} for label in ("descriptor", "descriptor", "alias")]}
    manifest = compiled(*extend_source([(quote, values)]))
    assert manifest["symptoms"].count("descriptor") == 1 and "alias" in manifest["symptoms"]


def test_edge_whitespace_is_equivalent_but_substring_granularity_is_unchanged():
    # Characterize the existing substring risk; a separate decision owns token/meaning boundaries.
    quote = "The source descriptor is unavailable."
    for phrase in ("available", " available ", "a"):
        manifest = compiled(*extend_source([row("symptoms", phrase, quote)]))
        assert manifest["label_bindings"]["symptoms"]["source_descriptor"]["phrase"] == phrase
