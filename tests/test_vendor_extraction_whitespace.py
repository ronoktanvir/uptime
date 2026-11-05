"""Hint generation and actual compilation share one source-preserving normalization."""
from hashlib import sha256

import pytest

from test_vendor_resource import compiled, extend_source
from uptime.vendor_resource_operators import interval_options


@pytest.mark.parametrize("space", [" ", "\n", "\r\n", "\t", "\u00a0"])
def test_duration_hint_and_compiled_effect_agree_without_rewriting_source(space):
    quote = "There is no" + space + "minimum incident duration."
    document, proposal = extend_source([(quote, {"interval_measurement":["no_minimum_duration"]})])
    manifest = compiled(document, proposal)
    assert "no_minimum_duration" in manifest["interval_measurement"]
    assert "no_minimum_duration" in interval_options(quote)
    citation = manifest["citations"][-1]
    assert citation["quote"] == quote
    assert document["text"][citation["start"]:citation["end"]] == quote
    assert citation["block_sha256"] == sha256(quote.encode()).hexdigest()
    assert manifest["document"]["sha256"] == sha256(document["text"].encode()).hexdigest()
