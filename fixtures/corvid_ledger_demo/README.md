# Corvid Ledger: second vendor for the November 10, 2026 film

Authored fixtures. Corvid Data Cooperative, Corvid Ledger and Harborline Analytics are fictional; no real vendor, monitor or customer supplied any of this.

| File | What it is |
|---|---|
| `extractions/7a43e383….json` | The recorded `claude-opus-5-5` reading of `fixtures/submission_onboarding/corvid_ledger.json` (job `26ee4e3f`, session `41f4dcb6`, November 9), copied unchanged from `docs/v4/evidence/submission-onboarding-20261109/corvid-ledger-initial.json` into the receipt format `staged_extraction` reads. No model was called to make it. |
| `overlay.json` | Account binding: the submission overlay with the account set to `harborline-corvid`. |
| `usage.json` | Authored: October 2026, 480 unavailable minutes (one 8-hour outage), month complete. |
| `invoice.json` | Authored: invoice `CDC-2026-10-0117`, issued 2026-11-01, one line of USD 10,000.00 for October 2026, no tax. |
| `estimate.json` | The instant the estimate is evaluated as if a request were received (2026-11-10). Nothing is filed. |

`scripts/setup_northwind.py` installs the agreement through the ordinary vendor routes with the scripted reviewer (`uptime/demo_opportunities.py:seed`). The workflow view's `opportunities` evaluates the usage and invoice with the installed ACTIVE agreement's own evaluator; the amount (USD 2,000.00 for these numbers) is never typed. It is an estimate: no claim is opened, nothing is approved, posted or applied, and it is never added to Northwind's figures.
