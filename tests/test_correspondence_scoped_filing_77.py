"""Authored signed receipt controls for the Decision77 historical deadline join."""
from copy import deepcopy
from datetime import UTC, datetime

import pytest

import test_correspondence_resource as resource_history
from test_v4_routes_integration import App
from test_vendor_resource import OVERLAY


@pytest.mark.parametrize("month,received,has_deadline", [
    ("2026-06", "2026-07-02T03:00:00Z", True),
    ("2026-07", "2026-08-02T03:00:00Z", False),
])
def test_signed_historical_receipt_uses_its_verified_month_and_original_received_time(
        tmp_path, monkeypatch, month, received, has_deadline):
    rows = deepcopy(resource_history.ROWS)
    rows[9] = (
        "Claims must be received no later than 2026-07-10T18:00:00Z for the June 2026 service month.",
        {"scoped_filing":{"month":"2026-06", "at":"2026-07-10T18:00:00Z", "endpoint":"inclusive", "basis":"received"}})
    monkeypatch.setattr(resource_history, "ROWS", rows)
    app = App(tmp_path / "historical-scoped.db")
    app.now = datetime(2026, 8, 12, tzinfo=UTC)
    app.scope.update(vendor="Copper Mesa Networks", account=OVERLAY["account"], contract=OVERLAY["agreement"],
                     service=OVERLAY["product"], component=OVERLAY["resource_id"], month=month,
                     invoice="scoped-invoice", incident="scoped-incident")
    app.provision()
    try:
        resource_history.install(app, tmp_path, monkeypatch)
        app.create()  # D04-C (2026-11-09): intake follows the installed governing terms
        body = dict(kind="original_filing_receipt", source_ref="signed-mailbox-77", receipt_id="original-77",
                    received_at=received, observed_at=app.now.isoformat(), submitted_to="claims@example.invalid",
                    fields=[dict(name="station identifier", refs=[OVERLAY["resource_id"]])])
        # Custody roles remain enforced before the historical join.
        assert app.source("customer-fixture", body).status_code == 403
        accepted = app.source("vendor-fixture", body)
        assert accepted.status_code == 200, accepted.text
        row = app.read()
        assert row["submissions"] == [] and row["actions"] == []
        assert row["ledger"]["claimed"] == row["ledger"]["awarded"] == "0.00"
        assert row["amount"] is None
        procedure = row["historical_procedure"]
        if has_deadline:
            assert procedure["filed_at"] == datetime.fromisoformat(received).isoformat()
            assert procedure["cutoff"] == "2026-07-10T18:00:00.000001+00:00"
            assert procedure["channel"] == "claims@example.invalid"
            assert procedure["original"] == "original-77" and procedure["original_digest"]
            assert procedure["missing"] == ["log references"]
        else:
            assert procedure is None
            assert row["outcome"] == "INSUFFICIENT_EVIDENCE"
            assert row["filing_cutoff"] is None
    finally:
        app.client.close()
