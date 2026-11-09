# D05 unseen-vendor proof: result

**Outcome: `NO_SUPPORTED_FAMILY`.** No candidate was staged, and nothing reached SHADOW, human approval or activation.

Under the [pre-registration](D05-SELECTION-PREREGISTRATION.md), this is an **acceptable refusal**: a concrete review requirement, **not a D05 success, and not unsafe**. D05's selection proof is therefore **not demonstrated** on this vendor.

## Run facts

| | |
|---|---|
| Authorization | Ronok's go-ahead in the evaluation session, November 9, 2026 ("Yes, run it") |
| Ran | 2026-11-09, frozen D05 branch `cccb5a0` = verified round-6 integration `3f60647` (4,664 passed) plus the gent8 scripts. App code is byte-identical to `3f60647`. Pre-call checks: all `true`. |
| Vendor (revealed) | **Backblaze**, *Backblaze Service Level Agreement*, `https://www.backblaze.com/company/policy/sla`, last updated March 27, 2019. Fourth in the hash order; the first three failed E1. |
| Commitments | `frame.json`, `selection.json`, `sealed-bundle.json` and `amendment-1.json` revealed in `../evidence/release-evaluation-gent8/d05/reveal/`. Each matches its SHA-256 in [the record](D05-SELECTION-RECORD.md). |
| Snapshot | Document SHA-256 `134729d1…7e8` (5,788 characters). Only the metadata is published; the vendor's page bytes and text stay outside Git. Anyone can re-fetch the page and re-run `scripts/d05_snapshot_gent8.py` (SHA-256 `86e56f5a…`). A later page change would show up as a different hash. |
| Path | Ordinary draft-signed routes with `profile: "auto"` (`scripts/d05_run_gent8.py`, branch `work/d05-run-gent8`). One inspect, two exact family requests, one start, polling to a terminal state. No retry. |
| Requests | Monthly (10,617 bytes) and resource (28,517 bytes). Each matched the server's `request_sha256`. **0** customer-overlay or sealed expected-term strings found in either. Approvals are for model invocation only, 6 h, $2.00 total cap. |
| Model calls | 2 genuine `claude-opus-5-5` calls: sessions `4c2158b1-3544-4ed1-bcec-d50f7cd4c5b5` and `4980f75e-8ba7-4b3f-a6ea-15bca2c2d94f`. Empty tool and MCP inventories, 0 tool events. Reported cost about $0.33. |

## Reported separately, as pre-registered

### 1. Raw extraction

- Both responses were bare strict JSON.
- **The model's monthly reading:**
  - Grounded **correctly**: the agreement (*Backblaze Service Level Agreement*), the vendor (*Backblaze, Inc.*) and the claim window (**30 days**).
  - Recognized the credit table header.
  - Marked as unsupported: the three credit-table rows (a 0% row and range rows such as "< 99.9% and ≥ 99.0%"); the per-user-account downtime and credit definitions; the SLO paragraph; the claim procedure details; the exclusions; and the site navigation text at the top and bottom of the page.
  - **Invented nothing:** no time zone, no maintenance window, no money.
- **The resource reading:** 98 blocks, mostly unestablished readings.

### 2. Validation and selection

- **Offline deterministic step:** refused, `RESOURCE_LANGUAGE_PRESENT`.
- **Monthly family:** `REFUSED_READING`, `EXTRACTION_FLAGGED_UNSUPPORTED`. The first cited passage is the page's navigation header.
- **Resource family:** `REFUSED_READING`. Unestablished and unsupported block readings; required terms missing (vendor, scope, measurement period, symptoms, provider-caused conditions, fee basis, remedy, filing deadline, effective dates).
- **Outcome:** `NO_SUPPORTED_FAMILY`, with the review requirement "No supported rule family represents this complete source…".

### 3. Supported-term coverage against the sealed expected terms

| Expected (sealed before the run) | Observed |
|---|---|
| Family: monthly; resource must not be selected | Resource **correctly not selected**; monthly **not selected** |
| Threshold 99.9%; tiers 5% below 99.9% down to 99.0%, 10% below 99.0% | **Not extracted.** The model flagged the table rows unsupported. |
| Claim window: 30 days after the end of the month | **Correct** in the raw reading (`filing_days` 30) |
| Remedy: credit on the next payment, no cash; fee basis per User Account | **Not extracted** (flagged unsupported) |
| Must not invent a time zone or maintenance window | **Respected** |
| Unsafe outcomes (wrong family, wrong terms, invented facts, money) | **None** |

### 4. Human approval

Not reached; there was no candidate. Ronok performed no action, and none was performed in his name. The promotion-path question (a CalyxQuay-only exception, a version-scoped exception, or a signed release) is moot for this vendor.

## Interpretation (bounded)

This is one sample.

Two factors are confounded:
- **The frozen input carried the site's navigation text.** The pre-registered extractor uses `<main>` when present, and this page has none. The model and the validator treated that text as unsupported material.
- **The SLA's own structure** sits at or beyond D07's narrow matrix: per-user-account downtime and credit, a range-condition table with a 0% row, an externally defined maintenance window, and an unstated time zone. A careful refusal may be the correct product behavior.

The run cannot separate these two factors. Neither can be fixed and rescored on this vendor: a cleaned input or a grammar change would be a named remediation.

The next D05 attempt needs a new independently selected vendor under a new pre-registration. That pre-registration should decide in advance how to handle page boilerplate.

## Private records (owner-only, outside Git)

`~/.local/share/uptime-engineering/review/d05-unseen-vendor/` holds:
- the frame and selection;
- the snapshot (page bytes and document);
- the run inputs (config, overlay, scenarios, forbidden terms);
- `run-1/`: raw queue evidence with the model responses, request exports and the workspace database.
