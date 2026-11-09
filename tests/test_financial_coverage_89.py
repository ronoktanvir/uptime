"""Decision 89: executable financial coverage matrix, boundary probes and name independence.

The matrix (docs/v4/coverage/financial-coverage-89.json) is descriptive. Engines
remain the only authority; every row must cite an existing test that exercises it.
New probes here cover boundaries the audit found without a direct test. Where a
probe pins a debatable classification, docs/v4/TEST-CHANGES-89.md says so.
"""
import ast
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
import json
from pathlib import Path
import re
import shutil

import pytest

import fixtures.northwind.loader as northwind
from uptime.contracts import Outcome, fingerprint
from uptime.correspondence_types import Scope
from uptime.governing_fees import FeeEntry, FeeRegistry, authenticated_invoice_snapshot
from uptime.pricing import Tier, evaluate_price
from uptime.pricing_demo import load_agreement, load_demo_inputs
from uptime.vendor_eval import evaluate
from uptime.vendor_terms import Overlay, bind_overlay

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/v4/coverage/financial-coverage-89.json"
HUMAN = ROOT / "docs/v4/FINANCIAL-COVERAGE-89.md"
REQUESTED = {"tax", "currency", "calendar", "proration", "amendment"}
AUDITED = REQUESTED | {"effective_dates", "usage_tiers", "fee_basis", "exclusions", "rounding", "deadlines"}


def _rows():
    return json.loads(MATRIX.read_text())["rows"]


def _symbols(path):
    tree = ast.parse((ROOT / path).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if isinstance(node, ast.ClassDef):
                names.update(f"{node.name}.{child.name}" for child in node.body
                             if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)))
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


# Matrix integrity --------------------------------------------------------------

def test_matrix_rows_are_typed_unique_and_cover_every_audited_dimension():
    matrix = json.loads(MATRIX.read_text())
    assert matrix["schema"] == "financial-coverage/1"
    ids = [row["id"] for row in matrix["rows"]]
    assert len(ids) == len(set(ids))
    for row in matrix["rows"]:
        assert set(row) == {"id", "engine", "dimension", "case", "status", "result", "enforced_by", "tests"}
        assert row["engine"] in matrix["engines"] and row["dimension"] in matrix["dimensions"]
        assert row["status"] in matrix["statuses"] and row["tests"] and row["enforced_by"]
    assert AUDITED <= {row["dimension"] for row in matrix["rows"]}
    for dimension in REQUESTED:  # each requested semantic has an explicit refusal, not only supported cases
        assert any(r["dimension"] == dimension and r["status"] != "SUPPORTED" for r in matrix["rows"])


def test_every_cited_test_and_enforcement_symbol_exists():
    for row in _rows():
        for reference in row["tests"]:
            path, name = reference.split("::")
            assert name in _symbols(path), (row["id"], reference)
        for reference in row["enforced_by"]:
            path, name = reference.split("::")
            assert name in _symbols(path), (row["id"], reference)


def test_human_matrix_lists_exactly_the_machine_rows():
    section = HUMAN.read_text().split("\n## Matrix\n", 1)[1].split("\n## ", 1)[0]
    published = re.findall(r"^\| `([A-Z]{2,5}-[A-Z0-9-]+)` \|", section, re.M)
    assert sorted(published) == sorted(row["id"] for row in _rows())
    assert len(published) == len(set(published))


def test_no_supported_money_row_relies_on_an_unstated_rounding_rule():
    for row in _rows():
        if row["status"] == "SUPPORTED" and row["dimension"] == "rounding":
            assert re.search(r"HALF_UP|exact|no rounding", row["result"]), row["id"]


# Negotiated pricing boundaries -------------------------------------------------

def _pricing():
    return load_agreement(), load_demo_inputs()[0][1]


def _closed(result, outcome):
    assert result.evaluation.outcome == outcome
    assert result.evaluation.amount is None
    assert result.overcharge is None and result.undercharge is None


def _with_last(agreement, **changes):
    return replace(agreement, versions=(*agreement.versions[:-1], replace(agreement.versions[-1], **changes)))


def test_contradictory_product_scope_never_prices():
    agreement, invoice = _pricing()
    last = agreement.versions[-1]
    both = _with_last(agreement, excluded_products=(*last.excluded_products, last.rates[0].product))
    twice = _with_last(agreement, rates=(last.rates[0], replace(last.rates[0], tiers=(Tier(None, D("1")),))))
    for contradictory in (both, twice):
        result = evaluate_price(contradictory, invoice)
        # Observed classification is INSUFFICIENT_EVIDENCE; the ledger records it as a review item.
        _closed(result, Outcome.MISSING)
        assert "Ambiguous covered/excluded product scope" in result.evaluation.trace[-1]


def test_amendment_dates_must_strictly_increase_and_precede_expiry():
    agreement, invoice = _pricing()
    first = agreement.versions[0]
    same_day = _with_last(agreement, effective_at=first.effective_at, signed_at=first.signed_at)
    at_expiry = _with_last(agreement, effective_at=agreement.expires_at)
    for changed, reason in ((same_day, "strictly increasing effective dates"), (at_expiry, "after agreement expiration")):
        result = evaluate_price(changed, invoice)
        _closed(result, Outcome.MISSING)
        assert reason in result.evaluation.trace[-1]


def test_performance_may_end_exactly_at_expiry_but_not_one_microsecond_later():
    agreement, invoice = _pricing()
    line = replace(invoice.lines[0], start=datetime(2026, 12, 1, tzinfo=UTC), end=agreement.expires_at)
    issued = replace(invoice, issued_at=datetime(2027, 1, 2, tzinfo=UTC), lines=(line,), total=line.net + line.tax)
    result = evaluate_price(agreement, issued)
    assert (result.lines[0].expected, result.lines[0].version, result.overcharge) == (D("20000.00"), "amendment-v2", D("7500.00"))
    late = replace(line, end=agreement.expires_at + timedelta(microseconds=1))
    _closed(evaluate_price(agreement, replace(issued, lines=(late,))), Outcome.INELIGIBLE)


def test_missing_evidence_outranks_an_unsupported_line_and_both_are_traced():
    agreement, invoice = _pricing()
    usage = invoice.lines[0]
    unallocated = replace(usage, allocation_ref=None)
    future = replace(usage, id="november", allocation_ref="november-ledger",
                     start=datetime(2026, 11, 1, tzinfo=UTC), end=datetime(2026, 12, 1, tzinfo=UTC))
    result = evaluate_price(agreement, replace(invoice, lines=(unallocated, future), total=unallocated.net + future.net))
    _closed(result, Outcome.MISSING)
    trace = "\n".join(result.evaluation.trace)
    assert "Unassessed line usage" in trace and "Unassessed line november" in trace and "future performance" in trace


# Monthly availability and completed-step boundaries -----------------------------

def _northwind():
    package = northwind.load_package()
    return package, package["manifest"], dict(package["overlay"]), dict(package["months"][0]["facts"]), package["tenant"]


def _january_context(package):
    row = package["months"][0]
    body = {"kind": "invoice", "lines": [{"id": x.id, "kind": "affected_api", "amount": str(x.net)} for x in row["invoice"].lines]}
    event = dict(source="billing", kind="invoice", body=body, digest=fingerprint(body), subject="scripted-financial-source",
                 source_key_id="unit-test-key", source_grant_id="unit-test-grant", received_at=row["facts"]["received_at"])
    snapshot = authenticated_invoice_snapshot(package["tenant"], Scope(**row["scope"]), event)
    return northwind.build_fee_registry(package).resolve(snapshot, as_of=datetime.fromisoformat(row["facts"]["received_at"]))


def test_receipt_before_month_end_is_outside_window_and_at_month_end_is_timely():
    package, manifest, overlay, facts, tenant = _northwind()
    early = evaluate(manifest, overlay, facts | {"received_at": "2026-01-31T23:59:59.999999+00:00"}, tenant)
    assert (early["outcome"], early["filing_status"], early["amount"]) == ("INELIGIBLE", "OUTSIDE_WINDOW", None)
    edge = evaluate(manifest, overlay, facts | {"received_at": "2026-02-01T00:00:00+00:00"}, tenant,
                    governing_fee=_january_context(package))
    assert (edge["outcome"], edge["filing_status"], edge["amount"]) == ("ELIGIBLE", "TIMELY", "2400.00")


@pytest.mark.parametrize("changes", [{"effective_until": "2026-01-30"}, {"effective_from": "2026-01-02"}])
def test_month_must_be_wholly_inside_both_governing_intervals(changes):
    package, manifest, overlay, facts, tenant = _northwind()
    bind_overlay(manifest, Overlay(**overlay | changes))  # onboarding accepts the partial overlap
    partial = evaluate(manifest, overlay | changes, facts, tenant, governing_fee=_january_context(package))
    assert (partial["outcome"], partial["amount"]) == ("UNSUPPORTED_RULE", None)
    # Exactly the whole month passes the window; the fee context stays pinned to the originally onboarded overlay.
    whole = evaluate(manifest, overlay | {"effective_from": "2026-01-01", "effective_until": "2026-01-31"}, facts, tenant,
                     governing_fee=_january_context(package))
    assert (whole["outcome"], whole["filing_status"], whole["missing"]) == ("INSUFFICIENT_EVIDENCE", "TIMELY", ["governing_fee_context"])
    assert evaluate(manifest, overlay, facts, tenant, governing_fee=_january_context(package))["amount"] == "2400.00"


@pytest.mark.parametrize("mutate", [
    lambda m: m.update(credit_rounding="nearest_cent_half_even"),
    lambda m: m.pop("credit_rounding"),
    lambda m: m.update(tiers=[]),
])
def test_completed_steps_need_exclusive_scope_and_explicit_half_up_even_with_a_valid_fee(mutate):
    package, manifest, overlay, facts, tenant = _northwind()
    changed = deepcopy(manifest)
    mutate(changed)
    result = evaluate(changed, overlay, facts, tenant, governing_fee=_january_context(package))
    assert (result["outcome"], result["amount"]) == ("UNSUPPORTED_RULE", None)


def test_incomplete_month_measurement_is_missing_evidence_not_a_zero_outage():
    package, manifest, overlay, facts, tenant = _northwind()
    result = evaluate(manifest, overlay, facts | {"month_complete": False}, tenant, governing_fee=_january_context(package))
    assert (result["outcome"], result["missing"], result["amount"]) == ("INSUFFICIENT_EVIDENCE", ["monitor"], None)


def test_contradicting_account_observation_is_reported_as_missing_scope():
    package, manifest, overlay, facts, tenant = _northwind()
    result = evaluate(manifest, overlay, facts | {"account": "harborline-002"}, tenant, governing_fee=_january_context(package))
    # Observed: a contradiction is classified like an absent fact. Recorded as a review item, not changed here.
    assert (result["outcome"], result["missing"], result["amount"]) == ("INSUFFICIENT_EVIDENCE", ["account"], None)


def test_non_usd_overlay_is_refused_at_onboarding():
    _, manifest, overlay, _, _ = _northwind()
    with pytest.raises(ValueError, match="Unsupported agreement or fee currency"):
        bind_overlay(manifest, Overlay(**overlay | {"currency": "EUR"}))


def test_governing_fee_line_with_nonzero_tax_is_refused():
    package = northwind.load_package()
    row = package["months"][0]
    bound = bind_overlay(package["manifest"], Overlay(**package["overlay"]))
    line = replace(row["invoice"].lines[0], tax=D("1.00"))
    taxed = replace(row["invoice"], lines=(line,), total=line.net + line.tax)
    entry = FeeEntry("taxed-january", package["tenant"], Scope(**row["scope"]), bound["plan"], bound["fee_line_ref"],
                     package["pricing_agreement"], taxed, package["manifest"]["document"]["sha256"],
                     fingerprint(package["manifest"]), fingerprint(bound))
    body = {"kind": "invoice", "lines": [{"id": line.id, "kind": "affected_api", "amount": str(line.net)}]}
    event = dict(source="billing", kind="invoice", body=body, digest=fingerprint(body), subject="scripted-financial-source",
                 source_key_id="unit-test-key", source_grant_id="unit-test-grant", received_at=row["facts"]["received_at"])
    snapshot = authenticated_invoice_snapshot(package["tenant"], Scope(**row["scope"]), event)
    with pytest.raises(ValueError, match="separate zero tax"):
        FeeRegistry((entry,)).resolve(snapshot, as_of=datetime.fromisoformat(row["facts"]["received_at"]))


# Fixture-name independence ------------------------------------------------------

RENAMES = (("Northwind Cloud", "Quillfeather Hosting"), ("NW-2026-001", "QF-2031-007"),
           ("Harborline Analytics", "Juniper Ledger Works"), ("harborline-001", "acct-7731"),
           ("Cloud Hosting", "Edge Compute"), ("cloud-hosting", "edge-compute"), ("Business plan", "Scale plan"),
           ('"Business"', '"Scale"'), ("NW-", "QF-"), ("Northwind", "Quillfeather"), ("northwind", "quillfeather"),
           ("Harborline", "Juniper"), ("harborline", "juniper"))


def _renamed_package(tmp_path, monkeypatch):
    target = tmp_path / "renamed"
    target.mkdir()
    for source in northwind.ROOT.iterdir():
        if source.suffix in {".json", ".txt"}:
            text = source.read_text()
            for old, new in RENAMES:
                text = text.replace(old, new)
            (target / source.name).write_text(text)
    # Integrity hashes and specimen signatures cover the original bytes; this renamed
    # copy is not an authored package. Only the financial engines are exercised here.
    monkeypatch.setattr(northwind, "verify_package", lambda root: json.loads((Path(root) / "package.json").read_text()))
    return northwind.load_package(target)


def _financial_rows(package):
    registry = northwind.build_fee_registry(package)
    rows = {}
    for row in package["months"]:
        body = {"kind": "invoice", "lines": [{"id": x.id, "kind": "affected_api", "amount": str(x.net)} for x in row["invoice"].lines]}
        event = dict(source="billing", kind="invoice", body=body, digest=fingerprint(body), subject="scripted-financial-source",
                     source_key_id="unit-test-key", source_grant_id="unit-test-grant", received_at=row["facts"]["received_at"])
        context = registry.resolve(authenticated_invoice_snapshot(package["tenant"], Scope(**row["scope"]), event),
                                   as_of=datetime.fromisoformat(row["facts"]["received_at"]))
        actual = evaluate(package["manifest"], package["overlay"], row["facts"], package["tenant"], governing_fee=context)
        rows[row["month"]] = dict(outcome=actual["outcome"], amount=actual["amount"], credit_units=actual.get("rate_units"),
                                  completed_steps=actual.get("completed_steps"), governing_fee=str(row["pricing_result"].lines[0].expected),
                                  price_exposure=str(row["pricing_result"].overcharge), price_version=row["governing_fee_version"],
                                  cutoff_exclusive=actual["claim_cutoff_exclusive"])
    return rows


def test_northwind_financial_results_do_not_depend_on_fixture_names(tmp_path, monkeypatch):
    original = northwind.load_package()
    renamed = _renamed_package(tmp_path, monkeypatch)
    assert renamed["manifest"]["vendor"] == "Quillfeather Hosting" and renamed["overlay"]["account"] == "acct-7731"
    assert renamed["pricing_agreement"].customer == "Juniper Ledger Works"
    assert renamed["manifest"]["document"]["sha256"] != original["manifest"]["document"]["sha256"]
    assert not any("Northwind" in json.dumps(row["scope"]) for row in renamed["months"])
    expected = json.loads((northwind.ROOT / "expectations.json").read_text())
    assert _financial_rows(renamed) == expected == _financial_rows(original)
    assert renamed["settlement"]["pricing_result"].overcharge == original["settlement"]["pricing_result"].overcharge


def _renamed_pricing(agreement, invoice):
    products = {"compute-job": "Edge Compute Jobs", "premium-support": "Concierge Help"}
    parties = {agreement.customer: "Juniper Ledger Works", agreement.vendor: "Quillfeather Hosting"}
    versions = tuple(replace(v, rates=tuple(replace(r, product=products[r.product]) for r in v.rates),
                             signatories=tuple(parties[s] for s in v.signatories),
                             excluded_products=tuple(products[p] for p in v.excluded_products)) for v in agreement.versions)
    agreement = replace(agreement, id="Order Form 7", customer=parties[agreement.customer], vendor=parties[agreement.vendor],
                        versions=versions)
    lines = tuple(replace(line, id="L-" + line.id, product=products[line.product],
                          allocation_ref=None if line.allocation_ref is None else "ledger " + line.allocation_ref) for line in invoice.lines)
    return agreement, replace(invoice, id="INV " + invoice.id, customer=agreement.customer, vendor=agreement.vendor, lines=lines)


@pytest.mark.parametrize("case", range(len(load_demo_inputs())))
def test_negotiated_pricing_results_do_not_depend_on_fixture_names(case):
    agreement, invoice = load_agreement(), load_demo_inputs()[case][1]
    original = evaluate_price(agreement, invoice)
    renamed = evaluate_price(*_renamed_pricing(agreement, invoice))
    assert (renamed.evaluation.outcome, renamed.overcharge, renamed.undercharge, renamed.stage) == (
        original.evaluation.outcome, original.overcharge, original.undercharge, original.stage)
    assert [(x.expected, x.delta, x.direction, x.version) for x in renamed.lines] == [
        (x.expected, x.delta, x.direction, x.version) for x in original.lines]
