"""Claimant custody cannot silently create issuer verification authority."""
import pytest
from copy import deepcopy

from test_vendor_resource import DOC, PROPOSAL, FACTS, compiled, extend_source, result


@pytest.mark.parametrize("quote", [
    "Supply a signed custodian statement verifying the intervals.",
    "The customer verifies its recording system and interval evidence.",
    "The provider publishes intervals. The custodian verifies the customer records.",
    "The provider instructions require a custodian verifying the interval evidence.",
    'Example: "The provider verifies the claim before issuing credits." This example does not apply.',
])
def test_customer_verification_words_do_not_establish_issuer_authority(quote):
    with pytest.raises(ValueError, match="verification"):
        compiled(*extend_source([(quote, {"evidence":["verification"]})]))


def test_explicit_provider_verification_remains_supported():
    quote = "The provider must verify the claim before issuing a service credit."
    manifest = compiled(*extend_source([(quote, {"evidence":["verification"]})]))
    assert "verification" in manifest["evidence"]


@pytest.mark.parametrize("proof_labels", [["verification"], ["verification", "verification"]])
def test_legacy_claimant_proof_with_custody_never_acquires_issuer_authority(proof_labels):
    proposal = deepcopy(PROPOSAL)
    original = proposal[-1]["quote"]
    proposal[-1]["quote"] = original.replace("After verification, ", "")
    proposal[-1]["value"].pop("evidence")
    quote = ("Include proof of failed samples in the claim. "
             "Supply a signed custodian statement verifying the intervals.")
    proposal.append(dict(quote=quote, field="resource_terms", value={
        "request_fields":["failed samples"], "evidence":[*proof_labels, "request_contents"]}))
    document = DOC | {"text":DOC["text"].replace(original, proposal[-2]["quote"]) + "\n" + quote}
    manifest = compiled(document, proposal)
    assert "claimant_supporting_proof" in manifest["evidence"]
    assert "verification" not in manifest["evidence"]
    facts = deepcopy(FACTS)
    facts["filing_proof"]["fields"]["failed samples"] = "n1,n2"
    evaluated = result(facts, manifest)
    assert evaluated["outcome"] == "ELIGIBLE"
    assert evaluated["issuance_status"] == "PENDING_VENDOR_VERIFICATION"


def test_internal_claimant_proof_label_cannot_be_proposed_as_new_authority():
    with pytest.raises(ValueError, match="Unsupported resource evidence category"):
        compiled(*extend_source([("The custodian provides proof of its recording system.",
                                  {"evidence":["claimant_supporting_proof"]})]))
