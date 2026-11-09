"""Finding F5 (Ronok, 2026-11-09: require reviewed binding).

A resource source that names no agreement cannot bind an overlay agreement by itself.
The overlay must carry the reviewed governing-terms attestation tying that exact
agreement to the exact document, effective date and unamended economics.
"""
import pytest

from governing_binding_89 import reviewed_binding
from test_vendor_service_month import OVERLAY, manifest
from uptime.vendor_terms import Overlay, bind_overlay


def test_unbound_overlay_for_an_unnamed_agreement_is_refused():
    terms = manifest()
    assert terms["agreement"] is None and terms.get("aggregate_monitor")
    with pytest.raises(ValueError, match="bound to its governing document"):
        bind_overlay(terms, Overlay(**OVERLAY))
    for other in ("Compass-8", "Any Agreement"):
        with pytest.raises(ValueError, match="bound to its governing document"):
            bind_overlay(terms, Overlay(**OVERLAY | {"agreement": other}))


def test_reviewed_binding_admits_exactly_its_agreement_and_document():
    terms = manifest()
    bound = bind_overlay(terms, Overlay(**reviewed_binding(terms, OVERLAY)))
    assert bound["agreement"] == "Compass-7" and bound["governing_terms"]["source_sha256"] == terms["document"]["sha256"]


@pytest.mark.parametrize("change", [
    {"agreement": "Compass-8"}, {"source_sha256": "0" * 64}, {"effective_from": "2027-01-01"},
    {"verified": False}, {"unamended_terms": ["scope"]}, {"evidence_sha256": "not-a-digest"},
])
def test_a_mismatched_or_incomplete_binding_is_refused(change):
    terms = manifest()
    overlay = reviewed_binding(terms, OVERLAY)
    overlay["governing_terms"] = overlay["governing_terms"] | change
    with pytest.raises(ValueError, match="verified local source"):
        bind_overlay(terms, Overlay(**overlay))


def test_another_agreement_cannot_reuse_a_binding_written_for_a_different_one():
    terms = manifest()
    overlay = reviewed_binding(terms, OVERLAY) | {"agreement": "Compass-8"}
    with pytest.raises(ValueError, match="verified local source"):
        bind_overlay(terms, Overlay(**overlay))


@pytest.mark.parametrize("extra", [
    {"override": {"filing_days": 9, "source_ref": "private-amendment", "quote": "Claims must be received within 9 calendar days after month end."}},
    {"symptom_aliases": {"down": "unavailable"}},
])
def test_the_fixed_service_month_profile_still_refuses_every_other_private_amendment(extra):
    terms = manifest()
    with pytest.raises(ValueError):
        bind_overlay(terms, Overlay(**reviewed_binding(terms, OVERLAY) | extra))


def test_a_source_that_names_its_agreement_still_binds_by_exact_equality():
    terms = manifest() | {"agreement": "Compass Master Agreement"}
    assert bind_overlay(terms, Overlay(**OVERLAY | {"agreement": "Compass Master Agreement"}))["agreement"] == "Compass Master Agreement"
    with pytest.raises(ValueError, match="Unsupported agreement"):
        bind_overlay(terms, Overlay(**OVERLAY))
