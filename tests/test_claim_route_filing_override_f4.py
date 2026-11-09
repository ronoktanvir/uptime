"""The signed claim route applies a private filing amendment only from its effective month (W3 F4, W0 route).

vendor_eval already honours effective_from (tests/test_vendor_filing_override_f4.py). The claim
route computed its monthly cutoff from the override for every month, so the two paths could
disagree on a filing deadline. These tests pin the route helper and the economic fingerprint.
"""
from copy import deepcopy

import pytest

from uptime import v4_routes
from uptime.contracts import fingerprint
from uptime.vendor_terms import Document, Overlay, bind_overlay, compile_terms
from test_vendor_catalog import DOC, OVERLAY
from test_vendor_filing_override_f4 import amended


def installed(overlay):
    manifest = compile_terms(Document(**DOC))
    return manifest, bind_overlay(manifest, Overlay(**overlay))


def test_route_cutoff_matches_the_evaluator_on_both_sides_of_the_amendment():
    manifest, overlay = installed(amended())          # source 12 days; amendment 19 days from 2026-07-01
    assert v4_routes._monthly_cutoff(manifest, overlay, "2026-06").isoformat() == "2026-07-13T00:00:00+00:00"
    assert v4_routes._monthly_cutoff(manifest, overlay, "2026-07").isoformat() == "2026-08-20T00:00:00+00:00"
    plain_manifest, plain = installed(OVERLAY)
    assert v4_routes._monthly_cutoff(plain_manifest, plain, "2026-07").isoformat() == "2026-08-13T00:00:00+00:00"


def test_an_undated_stored_amendment_is_unsupported_on_the_route():
    manifest, overlay = installed(OVERLAY)
    legacy = overlay | {"override": {k: v for k, v in amended()["override"].items() if k != "effective_from"}}
    with pytest.raises(ValueError, match="calendar month it governs from"):
        v4_routes._monthly_cutoff(manifest, legacy, "2026-06")


def test_fingerprint_without_an_amendment_keeps_its_exact_bytes():
    manifest, overlay = installed(OVERLAY)
    tiers = sorted((t["below_units"], t["credit_units"]) for t in manifest.get("tiers", [])
                   if t["product"] == overlay["product"] and t["plan"] == overlay["plan"])
    if "credit_rule" in manifest:
        before = fingerprint([manifest["family"], manifest["period"], manifest["remedy"], overlay["plan"],
                              manifest["credit_rule"], manifest["credit_rounding"], manifest["filing_days"]])
    else:
        before = fingerprint([manifest["family"], manifest["period"], manifest["remedy"], overlay["plan"], tiers,
                              manifest["filing_days"]])
    assert v4_routes._economics(manifest, overlay) == before


def test_fingerprint_binds_the_amendment_effective_month():
    manifest, july = installed(amended("2026-07-01"))
    _, april = installed(amended("2026-04-01"))
    _, plain = installed(OVERLAY)
    values = {v4_routes._economics(manifest, o) for o in (july, april, plain)}
    assert len(values) == 3
    assert v4_routes._economics(manifest, deepcopy(july)) == v4_routes._economics(manifest, july)
