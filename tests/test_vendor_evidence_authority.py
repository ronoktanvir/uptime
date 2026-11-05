"""Claimant custody cannot silently create issuer verification authority."""
import pytest

from test_vendor_resource import compiled, extend_source


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
