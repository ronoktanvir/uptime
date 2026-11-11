# Claim evidence for `halcyon-a` (authored)

Everything in this folder is authored for the November 10, 2026 claim demo (`uptime/template_claims.py`). Halcyon
Grid Services is a simulated local counterparty: its replies are fixed texts delivered through the workspace's own
signed source keys, never sent by any vendor. Save Time Inc, the account `savetime-halcyon`, the monitor reference,
the outage, the service log, the order form's fee and both invoices are invented. No monitor, vendor or customer
supplied any of it, and none of it goes to Ramp.

| File | What it is |
|---|---|
| `overlay.json` | The account binding the nine read terms do not carry: agreement `HGS-PAA-2026-0412` (the addendum number in `halcyon-a.txt`), account, covered service (Order Form HGS-OF-77120 named in clause 1.1), USD, fee line, and the addendum's effective date, October 1, 2026. |
| `usage.json`, `invoice.json`, `estimate.json` | The money link's month, in the shapes of `../halcyon-c/`: October 2026, 263 unavailable minutes, USD 8,000.00 monthly fees, evaluated as of 2026-11-03 12:00 UTC (the day the claim opens). |
| `lifecycle.json` | The same month in the claim workflow's shapes (as `fixtures/northwind/usage.json`, `invoices.json` and `supplements.json`): the claim scope, the one outage interval, the October invoice, the requested service log and its separate status verification, and the case clock's start. |
| `service-log.txt` | The service log `HGS-OCT-LOG-001` the counterparty asks for; its SHA-256 is pinned in `lifecycle.json`. |
| `correspondence.json` | The counterparty's two replies, shaped like `fixtures/northwind/correspondence.json`: a request for the dated service log, then an award of USD 2,000.00 (memo `HGS-CM-2026-10`). The award amount is a statement checked by the existing parser and evidence rules; it is not computed from the claim. |
| `next_invoice.json` | The next invoice the credit is applied to (shaped like `fixtures/northwind/settlement_invoice.json`): `HGS-INV-2026-12-2391`, December 2026 monthly fees, USD 8,000.00, unpaid, issued 2026-12-01, with clause 3.3 of `halcyon-a.txt` cited as the unchanged term that applies credits to the next invoice. |
| `agreement.json`, `order-monthly-rate.txt` | The fee: an authored order-form schedule fixing USD 8,000.00 a month for the Covered Services, in the existing fixed-monthly grammar, so the existing governing-fee resolver can prove the next invoice's fee. `halcyon-a.txt` itself states no fee amount. |

## The terms (from `halcyon-a.txt`)

Availability commitment 99.95% per calendar month (2.1). Below it and at or above 99.5%: a 10% credit; below 99.5%: 25%
(3.1). Credits for one month are capped at 30% (3.2). A credit is applied against the next invoice (3.3). A claim must
be submitted within 30 days after the end of the month (4.1). The addendum takes effect on October 1, 2026 (preamble, 6.3).

## The arithmetic

- October 2026 has 31 days: 31 × 1,440 = 44,640 minutes.
- One outage on October 14 from 06:12 to 10:35 UTC: 263 minutes, no Excluded Events.
- Available: 44,640 − 263 = 44,377 minutes. 44,377 / 44,640 = 99.4108…%.
- 99.4108…% is below 99.5%, so the second tier applies alone: 25%. The 30% cap is not reached.
- 25% × USD 8,000.00 = **USD 2,000.00**, estimated, claimed, awarded, posted and applied: one credit at five stages,
  never added together.
- The claim window closes 30 days after November 1, 2026: December 1, 2026 00:00 UTC (exclusive). The claim is filed on
  November 3.
- Next invoice before: USD 8,000.00 outstanding. The credit is applied once: USD 8,000.00 − 2,000.00 = **USD 6,000.00**
  outstanding.

## The case's timeline (its own clock, separate from Northwind's)

| When (UTC) | What |
|---|---|
| 2026-11-03 12:00 | The reviewer approves the October claim; the read terms are installed, the claim opens, the month's four signed records arrive, the claim is filed. |
| 2026-11-03 12:10 | The counterparty asks for the dated service log `HGS-OCT-LOG-001`. |
| 2026-11-04 09:00 / 09:05 | The log arrives from the customer source; the status source verifies it. |
| 2026-11-04 12:10 | After the 24-hour cooldown, the reviewer-approved response is sent. |
| 2026-11-05 13:00 | The counterparty awards USD 2,000.00. The reviewer posts it to the local ledger. |
| 2026-12-01 09:00 | The December invoice arrives through the signed billing source. The reviewer applies the credit once. |

What these show: a contract whose reader Claude agents built, read by that template alone, drives a credit through the
same claim, correspondence, ledger and invoice machinery as the Northwind case. What they do not show: any real outage,
reply, invoice or payment; that Halcyon would agree; that a real customer executed the addendum.

Limits of the demo around this evidence: the first decision approves the estimate shown, and the claim packet's
approval is recorded under it only after the engine's assessed claim matches that estimate. The case lives in its own
database, so it is not yet counted in the portfolio's "Who is doing the work", Activity, Cases or "Agreements on file".
