"""Opt-in strict whole-month scope in the claim-scope/1 table: exact marker, citation shape, grounding,
and legacy invariance (marker absent keeps "monthly keeps incident"; built-in Twilio unchanged).

All source text and manifests are authored here. No frozen corpus or private expected answer is read.
"""
from hashlib import sha256
import sqlite3

import pytest

from uptime import claim_scope
from uptime.claim_scope import (COMPLETE_SERVICE_MONTH, MONTHLY_FAMILY, MONTHLY_SERVICE_FAMILY, IncidentScope,
                                InvalidClaimScope, ServiceMonthScope, admit, complete_service_month, resolve,
                                variant_for)
from uptime.correspondence_types import Scope

WHOLE = dict(account="north-612", vendor="Boreal Relay", contract="BR-74", service="Message Store",
             currency="USD", month="2026-10")
TWILIO = dict(WHOLE, vendor="Twilio", service="Twilio Messaging API", contract="twilio-apis")
CLAUSE = ("Claims are based on a complete UTC calendar-month report for the entire service; "
          "incident identifiers are not required.")
HEAD = "Vendor: Boreal Relay"
TEXT = HEAD + "\n" + CLAUSE + "\n"


def manifest(text=TEXT, **changes):
    start = text.index(CLAUSE)
    base = {"family": MONTHLY_FAMILY, "document": {"sha256": sha256(text.encode()).hexdigest()},
            "citations": [{"id": 1, "start": 0, "end": len(HEAD), "quote": HEAD, "field": "vendor"},
                          {"id": 2, "start": start, "end": start + len(CLAUSE), "quote": CLAUSE,
                           "field": "evidence_basis"}],
            "evidence_basis": COMPLETE_SERVICE_MONTH, "period": "utc_calendar_month",
            "filing_days": 13, "remedy": "affected_monthly_fees_future_invoice",
            "tiers": [{"product": "Message Store", "plan": "Team"}]}
    base["citations"].extend([dict(id=3,field="period",start=0,end=len(HEAD),quote=HEAD),
                             dict(id=4,field="filing_days",start=0,end=len(HEAD),quote=HEAD)])
    return base | changes


def legacy():
    strict = manifest()
    del strict["evidence_basis"]
    strict["citations"] = strict["citations"][:1]
    return strict


def _no_tables():
    return sqlite3.connect(":memory:")


def test_exact_grounded_marker_selects_whole_service_month_with_no_obligation_fields():
    for source_text in (TEXT, None):  # grounded against source bytes, or shape-only where no text is at hand
        variant = variant_for(manifest(), {}, source_text=source_text)
        assert type(variant) is ServiceMonthScope
        assert variant.family == MONTHLY_SERVICE_FAMILY == "monthly-availability/1/complete_service_month/1"
        assert variant.required == frozenset() and not variant.builtin
        assert variant.check(Scope(**WHOLE)) is variant
        assert variant.check(Scope(**WHOLE | {"invoice": "oct-inv-3"})) is variant  # invoice is only an evidence reference


@pytest.mark.parametrize("field", ["incident", "component", "region"])
def test_whole_service_month_refuses_an_invented_obligation_field(field):
    variant = variant_for(manifest(), {}, source_text=TEXT)
    with pytest.raises(InvalidClaimScope, match=field + " not applicable and must be omitted"):
        variant.check(Scope(**WHOLE | {field: "x-1"}))


@pytest.mark.parametrize("terms", [legacy(), {"family": MONTHLY_FAMILY}])
def test_absent_marker_keeps_the_legacy_incident_scope(terms):
    variant = variant_for(terms, {}, source_text=TEXT)
    assert type(variant) is IncidentScope and variant.family == MONTHLY_FAMILY and variant.required == {"incident"}
    assert complete_service_month(terms) is False
    with pytest.raises(InvalidClaimScope, match="requires incident"):
        variant.check(Scope(**WHOLE))
    assert variant.check(Scope(**WHOLE | {"incident": "INC-1"})) is variant


@pytest.mark.parametrize("marker", ["complete_service_month/2", "Complete_Service_Month/1", "complete_service_month/1 ",
                                    "", "complete-service-month/1", None, True, 1, ["complete_service_month/1"]])
def test_any_other_present_marker_is_refused_not_read_as_legacy(marker):
    with pytest.raises(InvalidClaimScope, match="evidence basis is unsupported"):
        variant_for(manifest(evidence_basis=marker), {}, source_text=TEXT)


def test_marker_is_defined_only_for_the_monthly_availability_family():
    resource = manifest(family="resource-month/1", aggregate_monitor=True)
    with pytest.raises(InvalidClaimScope, match="evidence basis is unsupported"):
        variant_for(resource, {"resource_label": "station"})
    with pytest.raises(InvalidClaimScope, match="unsupported family"):
        variant_for(manifest(family="rebate/1"), {})


def _citation(**changes):
    strict = manifest()
    strict["citations"][1] = {k: v for k, v in (strict["citations"][1] | changes).items() if v is not ...}
    return strict


@pytest.mark.parametrize("terms", [
    legacy() | {"evidence_basis": COMPLETE_SERVICE_MONTH},                         # marker without citation
    manifest(citations=manifest()["citations"] + [dict(manifest()["citations"][1], id=3)]),  # two citations
    _citation(id=0), _citation(id="2"), _citation(id=True),
    _citation(start=10, end=10), _citation(start=30, end=20), _citation(start=-1), _citation(start="21"),
    _citation(quote=""), _citation(quote="   "), _citation(quote=None),
    _citation(value="complete_service_month/1"), _citation(quote=...),               # extra key / missing key
    _citation(id=1),                                                                # duplicate citation id
    manifest(citations="clause 2"), manifest(citations=[["not", "a", "dict"]]),
])
def test_citation_must_be_one_exact_source_span(terms):
    with pytest.raises(InvalidClaimScope, match="evidence basis is unsupported"):
        complete_service_month(terms)


@pytest.mark.parametrize("source_text", [
    "",                                                     # artifact without retained source text
    TEXT.replace("entire service", "entire servicE"),  # same offsets, different bytes
    TEXT + "Additional clause.\n",                          # quote still matches, document digest does not
    HEAD + "\n",                                            # span beyond the source
])
def test_citation_must_be_grounded_in_the_reviewed_source_bytes(source_text):
    with pytest.raises(InvalidClaimScope, match="not grounded"):
        complete_service_month(manifest(), source_text)


def test_grounding_rejects_a_digest_matching_document_whose_span_is_elsewhere():
    shifted = "Preface. " + TEXT  # the manifest's document digest is re-pinned, but the span is not moved
    terms = manifest()
    terms["document"] = {"sha256": sha256(shifted.encode()).hexdigest()}
    with pytest.raises(InvalidClaimScope, match="not grounded"):
        complete_service_month(terms, shifted)
    assert complete_service_month(manifest(shifted), shifted) is True


def test_resolve_grounds_installed_artifacts_and_refuses_ambiguity(monkeypatch):
    installed = []
    monkeypatch.setattr(claim_scope, "_installed", lambda db, tenant, scope: installed)
    installed[:] = [{"manifest": manifest(), "overlay": {}, "source_text": TEXT}]
    variant = resolve(_no_tables(), "bears", Scope(**WHOLE))
    assert type(variant) is ServiceMonthScope and admit(_no_tables(), "bears", Scope(**WHOLE)) == variant
    with pytest.raises(InvalidClaimScope, match="incident not applicable"):
        admit(_no_tables(), "bears", Scope(**WHOLE | {"incident": "INC-invented"}))
    installed[:] = [{"manifest": manifest(), "overlay": {}}]  # no retained source text: cannot ground the opt-in
    with pytest.raises(InvalidClaimScope, match="not grounded"):
        resolve(_no_tables(), "bears", Scope(**WHOLE))
    installed[:] = [{"manifest": manifest(), "overlay": {}, "source_text": TEXT.upper()}]
    with pytest.raises(InvalidClaimScope, match="not grounded"):
        resolve(_no_tables(), "bears", Scope(**WHOLE))
    installed[:] = [{"manifest": manifest(), "overlay": {}, "source_text": TEXT},
                    {"manifest": legacy(), "overlay": {}, "source_text": HEAD + "\n"}]
    with pytest.raises(InvalidClaimScope, match="ambiguous"):
        resolve(_no_tables(), "bears", Scope(**WHOLE))


def test_legacy_installation_still_requires_an_incident(monkeypatch):
    monkeypatch.setattr(claim_scope, "_installed", lambda db, tenant, scope: [
        {"manifest": legacy(), "overlay": {}, "source_text": HEAD + "\n"}])
    with pytest.raises(InvalidClaimScope, match="requires incident"):
        admit(_no_tables(), "bears", Scope(**WHOLE))
    variant = admit(_no_tables(), "bears", Scope(**WHOLE | {"incident": "INC-1"}))
    assert type(variant) is IncidentScope and variant.required == {"incident"}


def test_builtin_twilio_profile_is_unchanged():
    variant = resolve(_no_tables(), "bears", Scope(**TWILIO | {"incident": "INC-1", "component": "api"}))
    assert type(variant) is IncidentScope and variant.builtin and variant.required == {"incident", "component"}
    with pytest.raises(InvalidClaimScope, match="requires component, incident"):
        admit(_no_tables(), "bears", Scope(**TWILIO))
