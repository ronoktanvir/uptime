"""Authored sample of the Northwind April bill as a packaged verified Ramp read (demo line).

Built through the real records sanitizer (``sync_records``) from a read-only test double and
then the real packaging path (``package_verified_excerpt``), exactly as a person-started read
is packaged. It is not a Ramp read: the bill id is invented and no request reaches Ramp.
Regenerate the committed copy with ``uv run --locked python tests/ramp_demo_sample.py``.
"""
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_ramp_case_lineage import ENTITY, VENDOR, FakeRamp, raw_bill, raw_credit, uid  # noqa: E402
from uptime.ramp_context import package_verified_excerpt  # noqa: E402
from uptime.ramp_records import seal_snapshot, sync_records  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests/fixtures/ramp-records/northwind-nw-2026-04.json"
MARCH_SAMPLE = ROOT / "tests/fixtures/ramp-records/northwind-nw-2026-03.json"
BUSINESS = json.loads((ROOT / "docs/v4/evidence/demo-path-87/human-ramp-note.json").read_text())["business_id"]
NORTHWIND_BILL = uid(0x20260400)
MARCH_BILL = uid(0x20260300)
CREDIT_ID = uid(0x20260401)
AT = datetime(2026, 11, 10, 15, tzinfo=UTC)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def northwind_bill(bill_id=NORTHWIND_BILL, *, vendor_name="Northwind Cloud", invoice_number="NW-2026-04",
                   total=1100000, issued="2026-04-01T00:00:00+00:00", credit=None):
    row = raw_bill(bill_id, vendor=VENDOR, entity=ENTITY, total=total, status="OPEN", issued=issued,
                   applied=[(CREDIT_ID, credit)] if credit else ())
    row.update(approval_status="PENDING", invoice_number=invoice_number)
    row["vendor"]["name"] = vendor_name
    return row


def northwind_credit(bill_id=NORTHWIND_BILL, amount=240000, *, bill_side=True):
    """A vendor credit applied to the bill, as Ramp's credit list shows it."""
    return raw_credit(CREDIT_ID, total=amount, bills=[(bill_id, amount)] if bill_side else (), reference=bill_id)


def fake_ramp(bills, credits=()):
    ramp = FakeRamp(bills, credits)
    for vendor in ramp.rows["vendors"]:
        vendor["name"] = bills[0]["vendor"]["name"] if vendor["id"] == VENDOR else "Other vendor"
    return ramp


def northwind_capture(bill_id=NORTHWIND_BILL, credits=(), **bill):
    ramp = fake_ramp([northwind_bill(bill_id, **bill)], credits)
    snapshot = sync_records(ramp, page_size=10, detail_limit=10)
    snapshot = {**snapshot, "observed_at": AT.isoformat(), "completed_at": AT.isoformat()}
    return seal_snapshot({k: v for k, v in snapshot.items() if k != "checksum"})


def northwind_sample(bill_id=NORTHWIND_BILL, credits=(), **changes):
    snapshot = northwind_capture(bill_id, credits, **changes)
    bill = next(r for r in snapshot["resources"]["bills"]["records"] if r["id"] == bill_id)
    association = {"schema": "uptime-ramp-browser-association/1", "status": "ONE_BILL_READ_VERIFIED",
                   "origin": "https://demo-api.ramp.com", "business_id": BUSINESS, "bill_id": bill_id,
                   "browser_url": "https://demo.ramp.com/bill-pay/bills/list/" + bill_id,
                   "browser_url_source": "OPERATOR_SUPPLIED_OBSERVED_URL", "observed_at": AT.isoformat(),
                   "bill_record_sha256": _digest(bill), "verified_read_scopes": ["business:read", "bills:read"],
                   "write_attempted": False}
    return package_verified_excerpt(snapshot, association)


def march_sample(**changes):
    return northwind_sample(MARCH_BILL, invoice_number="NW-2026-03", total=1200000,
                            issued="2026-03-01T00:00:00+00:00", **changes)


if __name__ == "__main__":
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    for path, body in ((SAMPLE, northwind_sample()), (MARCH_SAMPLE, march_sample())):
        path.write_text(json.dumps(body, indent=1, sort_keys=True, allow_nan=False) + "\n")
        print(path)
