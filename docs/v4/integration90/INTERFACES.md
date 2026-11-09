# Published integration interfaces

**As of November 9, 2026, baseline `03b372e`.** These are the cross-workstream interfaces that specialists build against. Each section says whether it rests on an already accepted decision or is **frozen pending a team decision**. Frozen means the present behavior is published exactly as it is, and only the W0 owner may change it, after the team records the decision. [Ownership and change requests](OWNERSHIP.md) · [D03/D04 alternatives](D03-D04-ALTERNATIVES.md)

The November 3 CP1 wire contract in [docs/orchestration/INTERFACES.md](../../orchestration/INTERFACES.md) is the historical origin of these types. The V3 specification's proposed object list is mapped to these types in the [requirement checklist](REQUIREMENTS.md) (IF-1 to IF-7).

## 1. Account and agreement identity — frozen pending D03

| Consumer | Field(s) | Accepted domain today | Source |
|:---|:---|:---|:---|
| Signed claim intake (`POST /api/correspondence/claims`) | `scope.account`, `scope.contract` | `Id`: `^[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}$`. No spaces | `uptime/correspondence_types.py:7,18,20` |
| Signed claim intake | `scope.vendor`, `scope.service` | `Name`: letters, digits, internal spaces, `._/-`, max 96 | `uptime/correspondence_types.py:8,19,21` |
| Economic claim key (both intake routes) | tenant, vendor, account, agreement_id, service, month, remedy | Non-empty, no leading/trailing whitespace, no control characters. Vendor and service are NFC-normalized and case-folded; account and agreement are exact. `agreement_version` is required provenance but excluded from the key | `uptime/claim_identity.py:28-55` |
| Published contract → claim identity | `overlay.account`, `manifest.agreement` or `overlay.agreement`, `overlay.product` | Whatever onboarding accepted; spaces are allowed | `uptime/claim_identity.py:82-89`, `uptime/vendor_terms.py` |

**Published rule while D03 is open:** identity values are carried byte-exact. No route may slug, trim, case-fold or rewrite an account or agreement identity to make two domains agree. A value one route accepts and another rejects is a reproduced defect (receipts `docs/v4/evidence/pause-20261106/e86-01.json`, `e86-04.json`), not missing evidence. The identity specialist's characterization (`work/identity-pricing-89`) lists every domain that disagrees.

## 2. Claim scope — frozen pending D04

`Scope` (`uptime/correspondence_types.py:17-27`) is one strict, frozen shape with **ten required fields**: account, vendor, contract, service, component, invoice, incident, currency (`^[A-Z]{3}$`), month (`^20[0-9]{2}-(0[1-9]|1[0-2])$`) and region. No field is optional, and there is no resource field. Resource identifiers appear only in the evidence records (`ResourceSpan`, `ResourceLine`, `MonitorRow`, `MaintenanceRecord`, `IssuedCredit`).

**Published rule while D04 is open:** never invent a component, incident, region or invoice to satisfy the schema. A whole-service monthly obligation that cannot supply those fields is refused at intake today (HTTP 422). That refusal is reported as a D04 dependency, not as INSUFFICIENT_EVIDENCE.

## 3. Evaluation outcomes and money — agreed

- `Outcome` (`uptime/contracts.py`): `ELIGIBLE`, `INELIGIBLE`, `INSUFFICIENT_EVIDENCE`, `UNSUPPORTED_RULE`. `EvaluationResult` requires at least one `Citation` and a trace. `INSUFFICIENT_EVIDENCE` must name what is missing. Only `ELIGIBLE` may carry an amount, and it cannot be negative.
- `Money` is a finite `Decimal` in USD only; other currencies raise. Unknown amounts are `None`, never zero.
- `fingerprint` is SHA-256 over sorted, compact, float-free JSON. Stored hashes depend on it, so changing it is a migration.

## 4. Evidence references — agreed

- `EvidenceFact(ref, tenant, kind, source, digest, observed_at)`, with `source` drawn from `Source`: `LIVE_RAMP_SANDBOX`, `LIVE_VENDOR_PUBLIC`, `SYNTHETIC_CUSTOMER`, `SIMULATED_VENDOR`, `DETERMINISTIC_REPLAY`, `UNAVAILABLE`. These classifications stay in APIs and audit exports. Product screens use ordinary document references (November 4 direction, [ADR-0064](../decisions/ADR-0064-clean-walkthrough.md)).
- Signed evidence enters through enrolled source grants (`uptime/source_config.py`) and the inbox delivery records in `correspondence_types.py`. Each record carries its own `Id` references and a SHA-256 digest. A client cannot declare itself an authorized source.
- W5 owns source custody. A W5 change that alters which evidence is in scope (for example interval/month overlap) must list every affected expectation and keep the Northwind outcomes unchanged.

## 5. Financial stages — agreed

Stages are separate records and are **never summed**:

| Stage | Dashboard key (`uptime/workbench.py` `_metrics`) | Durable record |
|:---|:---|:---|
| Invoice exposure | `exposure` | Pricing finding; unknown stays "Not verified" |
| Estimated credit | `estimated` | `ELIGIBLE` evaluation amount |
| Claim filed | `claimed` | Claim receipt (`claim_identity` reservation, inbox claim) |
| Vendor awarded | `awarded` | `allocation_award`; source currently constrained to the simulated counterparty |
| Credit recorded | `posted` | `allocation_credit` (Local ledger) or a read Ramp vendor credit (`ramp_credit_sync`) |
| Applied to bills | `applied` | `allocation_application` with exact bill and remaining balance |

The current Northwind reference values are January USD 2,400 credit applied to the April USD 11,000 invoice, leaving USD 8,600. The March USD 1,000 price finding stays open and separate. A Local ledger record is not a Ramp credit. A vendor award is not cash.

## 6. Action authorization — agreed

- **Principals** (`uptime/contracts.py` `Principal`): tenant, subject and role. Enrolled human roles are `viewer` or `reviewer` (`uptime/auth.py:95-98`). Subjects starting with `scripted-`, `service-` or `local-` cannot enroll as humans. `scripted-test-reviewer` is never an actual human.
- **Write check** (`Workbench.check_write`): same tenant, `reviewer` role, and a workspace policy other than `OBSERVE`.
- **Policy modes** (`uptime/policy.py`): `OBSERVE`, `ASSISTED` (default, cap USD 0.00) and `POLICY_AUTOMATED` (requires an explicit positive cap, max USD 10,000, and applies only to the simulated counterparty). Which actions may run under standing policy is pending **D06**.
- **Signed requests**: P-256 proof of possession bound to origin, path, body hash and nonce. Issuer mandates and the release gate (`uptime/mandates.py`, `uptime/gates.py`) govern promotion and financial effects.
- **Local review exception** (`uptime/local_review_exception.py`): scope `interpret,approve,activate,rollback` for one CalyxQuay version only. The single recorded grant is COMPLETED (REVOKED at revision 9). It never covers claims, disputes, awards, credits, bills, payments or Ramp writes.
- **Native Ramp writes:** no agent may perform or reroute the blocked native-posting operation. An observed `bills:write` grant is not authorization.

## Interface changes since baseline on `work/integration-90`

| Change | Interface effect |
|:---|:---|
| `web/auth.js` sends `path` and `body_sha256` explicitly and accepts `.jwk` | None. These are the challenge model's existing defaults; the local review guard requires them explicitly |
