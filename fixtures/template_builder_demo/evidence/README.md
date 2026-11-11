# Template builder evidence: one authored service month for `halcyon-c`

Authored samples for the money link (`uptime/template_agreements.py`, `docs/demo/TEMPLATE-BUILDER.md`, "The money
link"). Halcyon Grid Services, Brightwater Freight Co., the account, the monitor reference and the invoice are invented;
no monitor, vendor or customer supplied any of this. The shapes mirror `fixtures/corvid_ledger_demo/`.

| File | What it is |
|---|---|
| `halcyon-c/overlay.json` | Account binding the seven read terms do not carry: agreement `HGS-PAA-2026-0457` (the addendum number in `halcyon-c.txt`), account, covered service (Order Form HGS-OF-78031), USD, fee line, and the effective date 2026-08-03 stated in the addendum. |
| `halcyon-c/usage.json` | Authored: October 2026, 95 unavailable minutes (one outage), month complete, Excluded Events removed. |
| `halcyon-c/invoice.json` | Authored: invoice `HGS-INV-2026-10-3318`, one line of USD 12,000.00 monthly fees for October 2026, no tax. |
| `halcyon-c/estimate.json` | The instant the estimate is evaluated as if a claim were received (2026-11-10, inside the 60-day window). Nothing is filed. |

Why October 2026: the addendum takes effect on August 3, 2026, and the engine evaluates only a complete calendar
month the agreement governs. October 2026 is such a month, and it is the same month as the other vendor's estimate on
the portfolio. The usage and the invoice are authored; they are not a record of anything that happened.

What these show: once a reviewer-approved template has read `halcyon-c` and every read guard passed, the terms it read
drive the existing credit engine: 44,545 of 44,640 minutes available (99.787%) is below the second-tier threshold of
99.9%, so the engine gives 35% of USD 12,000.00 = USD 4,200.00, an ESTIMATED credit on a SHADOW agreement.

What they do not show: any real outage, monitor reading, invoice or customer; that a claim was or could be filed,
approved, posted or applied (none is); that Halcyon's own monitoring would agree; that the template reads contracts of
another form. The month is stated to the engine as a UTC calendar month although the addendum names no time zone.
A contract read with no folder here (for example a pasted one) gets an agreement with no credit: "Needs usage evidence".
