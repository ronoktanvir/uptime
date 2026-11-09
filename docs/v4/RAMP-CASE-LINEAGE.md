# One Ramp case from financial record to reconciliation

Decision 93 joins the existing Ramp pieces into one checked case. A case is one evaluated Ramp financial record (a bill, draft bill or card transaction). It keeps the same identity through applicability, the finding, the native surface, the award, the Ramp vendor credit and the bill application. The first disagreement stops the chain with a fixed reason code, and later stages are reported as `NOT_EVALUATED`. Nothing in this workstream writes to Ramp.

[Decision record and Opus critique](decisions/ADR-0093-ramp-case-lineage.md) · [Test changes](TEST-CHANGES-93.md) · [Platform verification](evidence/ramp-lineage-93/platform-verification-20261109.json) · [Live read summary](evidence/ramp-lineage-93/live-read-20261109.json) · [Real case lineage](evidence/ramp-lineage-93/lineage-f74ba12c.json)

## Verified Ramp capabilities, November 9, 2026

The public OpenAPI was refetched at 11:01 UTC: 2,615,908 bytes, SHA-256 `29571a47002f5d08d5c7686a31551bb9b66a6c40f06b66597b3f1f5b26d35808`. It has the same 277 operations as the November 5 pin `2f7d60ff…`. The 28 changed schema paths concern audit-log events, approval assignment source, purchase-order denial descriptions and spend-intent questions, none of which this work uses. The environment is the Ramp demo sandbox: API `https://demo-api.ramp.com`, UI `https://demo.ramp.com`.

| Need | Operation | Scope | What it establishes |
|---|---|---|---|
| Vendor credits | `GET vendors/credits`, `GET vendors/credits/{id}`, `GET vendors/{id}/credits` | `vendors:read` | The total, remaining and applied amounts; `applied_bills` and `applied_draft_bills`; `reference_number` (the vendor's memo number). Active credits are listed by default. `include_fully_used` and `is_archived` are separate filters, and archived credits cannot be applied. |
| Create or apply a credit | None published | n/a | Only the Ramp UI can create or apply a credit (see the operator procedure below). |
| Bill read-back | `GET bills/{id}` | `bills:read` | `applied_vendor_credits`, `status` (`OPEN`/`PAID`), `approval_status` and `status_summary` (which includes `ON_HOLD`). |
| Informational note | `POST`/`GET comments/{object_type}/{id}` | Resource write/read | Allowed on bills, draft bills, transactions and spend requests. A note has no payment or approval effect. |
| Payment hold | `POST bills/{id}/hold`, `POST bills/{id}/release` | `bills:write` | "Blocks all payment rails." Read back through `status_summary`. **Not executed.** |
| Approval step | `POST approvals/{entity_type}/{entity_id}/add-step` | `approval_chains:write` | Published as still in development. The scope isn't granted to the demo app. |
| Blank Canvas decision | `POST blank-canvas-approvals/{approval_trigger_instance_id}` | `blank_canvas:write` | Acts on a configured procurement trigger instance, not on a bill. No trigger is configured. |
| Agreements | `POST vendors/agreements` (list query) | `vendors:read` | Agreement metadata only. It doesn't supply governing terms. |

The demo app already holds `bills:write`, and the agent-run native posting retest is still refused by automatic approval review. That retest was neither retried nor rerouted. Ramp's help article (HTML SHA-256 `6ac21805…`) supplied the operator facts below. Its text was not copied.

## Applicability: `uptime/ramp_association.py`

`associate(snapshot, ContractScope, NativeAssociation, provider_business_id=…)` classifies every observed record for one contract:

- `APPLICABLE`: the native vendor UUID, entity, currency and issue date all fall within the reviewed association and the contract's half-open effective period.
- `NOT_APPLICABLE`: a verified mismatch, such as a different vendor, entity, currency, period or reviewed allowlist.
- `UNKNOWN`: missing evidence, such as a missing issue date or currency. Card transactions also land here unless reviewed by ID, because Ramp's merchant namespace isn't the bill-pay vendor namespace.
- `CONFLICT`: a reviewed allowlist entry that the provider record contradicts.

POs and Ramp agreements are context only (`LINKED_CONTEXT`). Reviewed IDs that are missing from a complete list are reported, and an incomplete list never proves absence. Names, amounts, date proximity and the contract's vendor label are never compared with Ramp data.

`ContractScope` takes exact identities and never rewrites them. Account and agreement IDs follow team decision D03-A through the shared `uptime.source_identity` rule (`source-identity/1`): 1–96 characters; letters, digits, single spaces and `. , ' & ( ) + : / _ -`; at least one letter or digit; already NFC. Anything else is refused, never trimmed, normalized or case-folded, so this layer accepts exactly what claim intake, onboarding and the ledger accept. Association results record `identity_version`. Tenant, contract version, vendor label, claim, award and actor labels keep local bounds: up to 512 characters, no surrounding whitespace or control characters, already NFC. `scope_from_claim_identity` maps the existing field names without changing any value. When the D03 identity contract lands, it replaces this adapter and nothing else.

## Lineage: `uptime/ramp_case_lineage.py`

`build_lineage(CaseIdentity, snapshot=…, provider_business_id=…, finding=…, association=…, price_binding=…, surface=…, award=…, credit_binding=…, readbacks=…, binding_registry=…)` checks these stages in order:

1. **Financial record.** The capture comes from the installation-verified business and contains the exact record. Its vendor, entity and currency match the case.
2. **Applicability.** A contract case needs a reviewed association computed for this same capture, and the record must be `APPLICABLE`. A case without contract fields is an evidence-gap case, and no award or credit may attach to it.
3. **Finding.** The record ID, capture checksum, record digest and finding digest are recomputed. A price finding's bound agreement must have the case's contract ID, the same vendor and entity, and the same record. A monetary finding without bound terms is refused.
4. **Surface.**
   - *Approved person-posted evidence-gap note.* It is an informational comment with no payment or approval effect. It is accepted only on an `INSUFFICIENT_EVIDENCE` finding for the same business and bill, and it is re-observed by comment ID and timestamp. If a later complete read of that bill's thread lacks the note, the lineage needs review.
   - *Payment hold.* It counts only while a read after the recorded request still shows `ON_HOLD`. A hold that existed before the request isn't attributed to it, and a hold a later read no longer shows is reported as `HOLD_NOT_CURRENT`.
   - *Approval-step and Blank Canvas surfaces.* These are never credited, because no configured integration exists.
   - *Uncertain Uptime outbox delivery.* It is read back in the same thread and never resent.
5. **Award.** An award already confirmed elsewhere, with the same claim, contract, account, native vendor and currency. This module never creates an award.
6. **Credit.** A reviewed `CreditBinding` links one native credit to one award. Every binding for the tenant is checked together: one credit bound to two cases, or one award split across credits, needs attribution review, even when the credit hasn't been observed yet.
7. **Application.** The applied amount is the sum of credit-to-bill applications that both the credit and the bill report with equal amounts, on bills that are applicable to the contract. If any pair can't be verified, the applied amount is null.

The money fields are separate and have no total: finding estimate, claimed (always null here), awarded, recorded credit, remaining credit, applied, and draft reserved. `actual_recovery` is always null. A recorded credit with no application reports applied `0`, which is an observed fact; it isn't missing data.

### Reconciliation over time

Read-backs are ordered by observation time, and repeated captures with the same checksum count once.

- **Partial application.** Reported as `PARTIALLY_APPLIED`, with the remaining credit taken from Ramp.
- **Draft-bill reservations.** Reported only as `draft_reserved_minor`.
- **Review triggers.** Each of these makes the lineage `REVIEW_REQUIRED` with applied set to null, and the history keeps every value:
  - a decreased pair amount (Ramp lets a person remove a credit from a bill);
  - a linked credit missing from a later complete list (the default list excludes archived credits, so absence isn't a reversal);
  - changed credit identity;
  - a credit larger than its award;
  - two different captures with the same timestamp.
- **Truncated or one-sided latest read.** Applied is `UNKNOWN`.
- **Unbound credits from the same vendor.** Never attributed.

The existing `RampCreditSync` journal and `AllocationLedger` are unchanged, and they still accept only simulated awards. This lineage is a read-side check over the same Ramp facts. Merging it with the ledger is follow-up work for after D09.

## Person-operated credit procedure (prepared, not executed)

Ramp publishes no create or apply operation for vendor credits. When D09 is decided:

1. **Create the credit.** A person with Bill Pay and vendor permissions creates the vendor credit in Ramp, either from the paid reference bill (three-dot menu → New Vendor Credit) or from the vendor's profile (New → Vendor credit). They enter the vendor's memo number and an amount no larger than the verified award, in the bill's invoice currency.
2. **Read it back.** Run a fresh read-only `scripts/ramp_sync.py`. A reviewer then records a `CreditBinding` that names that exact credit ID and award. The lineage must then show `RECORDED` or `PARTIALLY_CREDITED`.
3. **Prepare the application.** `prepare_operator_application` writes the exact instruction and the expected post-state. It requires:
   - a clean lineage, re-verified by its digest;
   - a `VERIFIED_VENDOR_AWARD` (a walkthrough's simulated award never qualifies);
   - an association computed for the current capture;
   - a usable credit with enough balance;
   - an unpaid, applicable bill of the same vendor, entity and currency that won't be over-applied.
4. **Apply it in Ramp.** On the target bill, before payment starts or is batched, the person chooses **Apply available vendor credits → Split payment → Vendor credit**, selects that exact credit and enters that exact amount. If only the legacy **Apply vendor credits** toggle appears, they stop: that toggle picks credits by accounting date and may apply a different one.
5. **Confirm by read-back.** `confirm_operator_application` classifies a later read as one of the outcomes below. Nothing is retried. It also records who acted; whether one person may both prepare and execute is decision D06.

| Outcome | Meaning |
|---|---|
| `CONFIRMED_BY_READBACK` | The application matches the instruction exactly. |
| `CONFIRMED_CREDIT_ALSO_USED_ELSEWHERE` | The application matches, and the same credit was also used on another bill. |
| `CONFIRMED_WITH_OTHER_CREDITS_ON_BILL` | The application matches, and other credits also appear on the bill. |
| `NOT_YET_OBSERVED` | The read shows no change yet. |
| `ONE_SIDED_UNCERTAIN` | Only one side (credit or bill) shows the change. |
| `DIFFERENT_AMOUNT_APPLIED` | An amount other than the prepared one was applied. |
| `OTHER_CREDIT_APPLIED` | A different credit was applied, as the legacy toggle can do. |
| `APPLICATION_DECREASED` | The applied amount went down. |
| `UNVERIFIABLE` | The read can't establish the outcome. |
| `BUSINESS_MISMATCH` | The read belongs to a different Ramp business. |
| `READ_NOT_AFTER_PREPARATION` | The read isn't later than the preparation. |

These functions are tested but not exposed through any route or CLI until D09 is decided.

## The real case: demo bill `f74ba12c`

A read-only verification and records sync at 11:02–11:03 UTC on November 9 confirmed:

- **Business and bill:** business `1569e402-460e-4952-adad-9df27db628a0`; bill `f74ba12c-95d0-582d-9f62-26d8057d1d37`, USD 840, `OPEN`, approval `PENDING`, one expense line with no quantity or unit price. The bill reports no applied credits.
- **Vendor credits:** the list was complete and empty (fully used credits included; archived credits not requested).
- **Agreements:** the list was complete and empty.
- **Comment:** the only comment is `376563cf-950c-409d-b3d8-a68599c45fa0`, on that bill, with the same `2026-11-08T01:46:45Z` timestamp as the human note receipt.

The lineage gives:

`OBSERVED → NO_GOVERNING_AGREEMENT → INSUFFICIENT_EVIDENCE → VERIFIED_READBACK (human-posted informational comment, re-observed) → no award → no bound credit → application not applicable`

Every case money field is null. The plan is `NONE / ALREADY_SURFACED_AND_VERIFIED`, so the note is not posted again. The committed human-note receipt is unchanged byte for byte (a test pins its hash). This is the only real case: no Ramp vendor or bill has been matched to the authored Northwind contract, and the lineage refuses to attach Northwind terms to this bill.

## Decisions that block further native work

- **D02:** Which real Ramp vendor and bill carry a contract case. Without it there is no reviewed `NativeAssociation` for real data, and Northwind stays a local-ledger walkthrough.
- **D03:** Decided on November 9 as D03-A, bounded exact source identity. Account and agreement IDs here use agent1's `source-identity/1` rule. The near-duplicate filing guard applies at claim filing in `claim_identity`, not in this read-side lineage.
- **D06:** Decided on November 9 as "humans gate judgment". Here, a person performs every native credit step and no model output affects any gate. Whether the preparer and executor must be different people isn't settled by that summary, so `confirm_operator_application` records `separation_of_duties` without enforcing it. Who may request a hold is still open.
- **D09:** How credits are created and applied, and who verifies that an award belongs to a claim. This also covers exposing the operator-application functions and merging with `AllocationLedger`.

## External proof still missing

- An actual vendor award.
- A Ramp vendor credit created in the selected business, and its application to a bill confirmed by read-back.
- A Ramp object that carries a contract case under D02.
- Any Uptime-origin API write, payment hold or configured approval intervention.
- Proof of who authored the human note: Ramp's `user_id` proves no identity.

None of these can be produced by code, and none was attempted here.

## Rollback

Revert the decision 93 commits. Two new modules, one offline CLI, one test file, documentation and evidence files were added; no existing module, table or test changed. The private runtime receipts under `~/.local/share/uptime-engineering/runtime/ramp-lineage-20261109/` (mode 0700) can be kept for audit.
