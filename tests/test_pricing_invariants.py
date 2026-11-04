"""Dependency-free invariants, also collected by pytest.

Can run through unittest when the shared pytest installation cannot be read.
"""
from dataclasses import replace
from datetime import timedelta, timezone
from decimal import Decimal as D
import unittest

from uptime.contracts import Outcome, Source
from uptime.pricing import ProviderBill, PricingInputError, bind_sandbox_bill, evaluate_price
from uptime.pricing_demo import load_agreement, load_demo_inputs


class PricingInvariants(unittest.TestCase):
    def setUp(self):
        self.agreement = load_agreement()
        self.invoice = load_demo_inputs()[0][1]

    def test_quantity_monotonicity_and_threshold_marginals(self):
        previous = D("0")
        for quantity in range(1, 2002):
            line = replace(self.invoice.lines[0], quantity=D(quantity))
            invoice = replace(self.invoice, lines=(line,), total=line.net)
            result = evaluate_price(self.agreement, invoice)
            current = result.lines[0].expected
            self.assertEqual(current - previous, D("15") if quantity <= 1000 else D("10"))
            previous = current
        self.assertEqual(previous, D("25010"))

    def test_signed_difference_and_money_stage_invariants(self):
        for status in ("pending", "paid"):
            for offset in (D("-7500"), D("0"), D("7500")):
                line = replace(self.invoice.lines[0], net=D("20000") + offset)
                invoice = replace(self.invoice, payment_status=status, lines=(line,), total=line.net)
                snapshot = repr(invoice), repr(self.agreement)
                result = evaluate_price(self.agreement, invoice)
                self.assertEqual(result.lines[0].delta, offset)
                self.assertEqual(result.overcharge, max(D("0"), offset))
                self.assertEqual(result.undercharge, max(D("0"), -offset))
                self.assertEqual(result.evaluation.outcome, Outcome.ELIGIBLE if offset > 0 else Outcome.INELIGIBLE)
                self.assertEqual((repr(invoice), repr(self.agreement)), snapshot)

    def test_performance_resolution_invariant_across_timezones(self):
        boundary = self.agreement.versions[1].effective_at
        for hours in (-12, -7, 0, 5, 14):
            for offset in (-1, 0, 1):
                start = (boundary + timedelta(seconds=offset)).astimezone(timezone(timedelta(hours=hours)))
                line = replace(self.invoice.lines[0], start=start, end=start + timedelta(seconds=1))
                invoice = replace(self.invoice, lines=(line,), total=line.net)
                result = evaluate_price(self.agreement, invoice)
                self.assertEqual(result.lines[0].expected, D("27500") if offset < 0 else D("20000"))

    def test_missing_evidence_never_has_claim_value(self):
        for changes in ({"product": None}, {"quantity": None}, {"allocation_complete": False},
                        {"allocation_ref": None}, {"start": None}, {"tax": None},
                        {"start": self.invoice.lines[0].start - timedelta(days=1)}):
            line = replace(self.invoice.lines[0], **changes)
            result = evaluate_price(self.agreement, replace(self.invoice, lines=(line,), total=line.net))
            self.assertEqual(result.evaluation.outcome, Outcome.MISSING)
            self.assertIsNone(result.evaluation.amount)
            self.assertIsNone(result.overcharge)
            self.assertFalse(result.lines)

    def test_provider_identity_money_status_and_origin_invariants(self):
        mapping = replace(self.invoice, id="test-only-bill", provider_vendor_id="test-only-vendor")
        provider = ProviderBill(mapping.id, mapping.total, mapping.currency, mapping.payment_status,
                                mapping.provider_vendor_id, Source.RAMP, True, "test-only-proof",
                                mapping.issued_at, "https://demo-api.ramp.com")
        bound = bind_sandbox_bill(provider, mapping)
        self.assertEqual(evaluate_price(self.agreement, bound).overcharge, D("7500"))
        self.assertEqual(bound.lines, mapping.lines)
        for change in ({"id": "conflict"}, {"amount": D("1")}, {"currency": "EUR"},
                       {"payment_status": "paid"}, {"verified": False}, {"source": Source.REPLAY},
                       {"base_url": "https://api.ramp.com"}, {"verification_ref": ""}):
            conflicting = replace(provider, **change)
            with self.assertRaises(PricingInputError):
                bind_sandbox_bill(conflicting, mapping)
            result = evaluate_price(self.agreement, replace(mapping, provider=conflicting))
            self.assertIsNone(result.evaluation.amount)
            self.assertIsNone(result.overcharge)
            self.assertNotIn(Source.RAMP, result.sources)
        self.assertEqual(provider.payment_status, "pending")
        self.assertIsNone(mapping.provider)


if __name__ == "__main__":
    unittest.main()
