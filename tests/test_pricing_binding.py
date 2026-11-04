"""Mocked provider integration; these tests are not proof of a live Ramp read."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D

import pytest

from uptime.contracts import Outcome, Source
from uptime.pricing import ProviderBill, ProviderLine, PricingInputError, bind_sandbox_bill, evaluate_price
from uptime.pricing_demo import load_agreement, load_demo_inputs


@pytest.fixture
def mapping():
    return replace(load_demo_inputs()[0][1], id="test-provider-bill", provider_vendor_id="test-provider-vendor")


@pytest.fixture
def provider(mapping):
    return ProviderBill(mapping.id, D("30000.00"), "USD", "pending", mapping.provider_vendor_id,
                        Source.RAMP, True, "test-only-read-receipt", datetime(2026, 11, 3, tzinfo=timezone.utc),
                        "https://demo-api.ramp.com")


def test_binding_keeps_live_money_separate_from_synthetic_scope(provider, mapping):
    bound = bind_sandbox_bill(provider, mapping)
    assert bound.id == provider.id and bound.total == provider.amount
    assert bound.lines == mapping.lines and bound.source == Source.CUSTOMER
    assert bound.provider == provider
    assert mapping.provider is None and provider.payment_status == "pending"
    result = evaluate_price(load_agreement(), bound)
    assert result.overcharge == D("7500.00")
    assert result.sources == (Source.RAMP, Source.CUSTOMER)
    assert "no real commercial relationship established" in "\n".join(result.evaluation.trace)
    assert provider.payment_status == bound.payment_status == "pending"


@pytest.mark.parametrize("change", [
    {"id": "different"}, {"amount": D("500.00")}, {"amount": 30000.0},
    {"currency": "EUR"}, {"payment_status": "paid"}, {"vendor_id": "other"},
    {"source": Source.REPLAY}, {"verified": False}, {"verification_ref": ""},
    {"observed_at": datetime(2026, 11, 3)}, {"base_url": "https://api.ramp.com"},
])
def test_binding_fails_closed_on_provider_conflicts(provider, mapping, change):
    provider = replace(provider, **change)
    with pytest.raises(PricingInputError):
        bind_sandbox_bill(provider, mapping)
    # Direct construction cannot bypass validation or label bad evidence live.
    result = evaluate_price(load_agreement(), replace(mapping, provider=provider))
    assert result.evaluation.outcome in (Outcome.MISSING, Outcome.UNSUPPORTED)
    assert result.evaluation.amount is None
    assert Source.RAMP not in result.sources


def test_live_small_bill_never_silently_substitutes_demo_fees(provider, mapping):
    with pytest.raises(PricingInputError, match="no fee substitution"):
        bind_sandbox_bill(replace(provider, amount=D("125.00")), mapping)


def test_total_match_does_not_allow_unreconciled_synthetic_lines(provider, mapping):
    bad = replace(mapping, lines=(replace(mapping.lines[0], net=D("10")), mapping.lines[1]))
    with pytest.raises(PricingInputError, match="allocation does not equal"):
        bind_sandbox_bill(provider, bad)


@pytest.mark.parametrize(("field", "value"), [
    ("net", D("1")), ("tax", D("1")), ("product", "different-product"),
    ("quantity", D("1")), ("unit", "seat"),
    ("start", datetime(2026, 9, 1, tzinfo=timezone.utc)),
    ("end", datetime(2026, 10, 31, tzinfo=timezone.utc)),
])
def test_every_known_provider_line_field_is_checked(provider, mapping, field, value):
    lines = tuple(ProviderLine(line.id, line.net, line.tax, line.product, line.quantity, line.unit, line.start, line.end)
                  for line in mapping.lines)
    assert bind_sandbox_bill(replace(provider, lines=lines), mapping)
    bad = replace(provider, lines=(replace(lines[0], **{field: value}), lines[1]))
    with pytest.raises(PricingInputError, match="conflicts"):
        bind_sandbox_bill(bad, mapping)


@pytest.mark.parametrize("lines", [(ProviderLine("unknown"),), (ProviderLine("usage"), ProviderLine("usage"))])
def test_provider_line_scope_must_match_exactly(provider, mapping, lines):
    with pytest.raises(PricingInputError):
        bind_sandbox_bill(replace(provider, lines=lines), mapping)


def test_paid_status_requires_explicit_agreement(provider, mapping):
    paid = bind_sandbox_bill(replace(provider, payment_status="paid"), replace(mapping, payment_status="paid"))
    result = evaluate_price(load_agreement(), paid)
    assert result.stage == "RETROSPECTIVE_REVIEW" and result.overcharge == D("7500")
    assert paid.payment_status == "paid"


def test_verified_bill_provenance_survives_missing_synthetic_scope(provider, mapping):
    missing = replace(mapping, lines=(replace(mapping.lines[0], product=None), mapping.lines[1]))
    result = evaluate_price(load_agreement(), bind_sandbox_bill(provider, missing))
    assert result.evaluation.outcome == Outcome.MISSING and result.evaluation.amount is None
    assert result.sources == (Source.RAMP, Source.CUSTOMER)


def test_binding_does_not_depend_on_global_decimal_precision(provider, mapping):
    from decimal import localcontext
    with localcontext() as ctx:
        ctx.prec = 3
        assert bind_sandbox_bill(provider, mapping).total == D("30000.00")
