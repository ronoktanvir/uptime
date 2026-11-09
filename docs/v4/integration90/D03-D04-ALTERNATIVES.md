# D03 and D04: alternatives and migration consequences for the team

**Status: DECIDED 2026-11-09, owner Ronok** ([decision record](#decision-record)). Implementation is in progress on `work/identity-pricing-89` and is **not yet merged or verified**. The analysis below is preserved as prepared. It covers the concrete choices for [D03 (account and contract identity) and D04 (contract-specific scope)](../TEAM-DECISION-HANDOFF.md#team-decision-sheet). The integration owner's preference is labelled as a preference. It was criticized once by Claude Opus 5.5; [the critique and how it changed this document](#opus-55-critique) are below. Record the team's choice beside D03/D04 in the handoff before any implementation starts.

## The defect both decisions resolve

A vendor adapter can be onboarded and activated, yet the matching claim cannot be created:

| Observation | Evidence |
|:---|:---|
| Onboarding accepts account and agreement names with spaces. Signed claim intake rejects them (`Id` pattern has no space) | `docs/v4/evidence/pause-20261106/e86-01.json`, `e86-04.json` (HTTP 422, no model call, no normalization) |
| The same intake requires component, incident, region and invoice for every claim. A whole-service monthly case lacks component/incident/region; a resource case lacks invoice/incident/region | Same receipts |
| Identity domains disagree in eight places. Examples: onboarding accepts a trailing-space account, which claim keys refuse; `ramp_terms_store` rejects spaces; dispute wire and reconciliation accept spaces and Unicode | Characterization by the identity specialist on `work/identity-pricing-89` (`tests/test_identity_domain_89.py`, `docs/v4/IDENTITY-SCOPE-CONTRACT-89.md` once committed) |
| Consequence beyond intake: in Northwind, a spaced account turns January from ELIGIBLE USD 2,400.00 into INSUFFICIENT_EVIDENCE. The governing-fee context becomes unreachable, so a non-evidence defect is reported as missing evidence | Same characterization |

Two further paths any option must reconcile (also found by the identity specialist):

- `uptime/allocations.py:53-62` `canonical` applies NFC normalization and `strip()` to ledger scope fields. It is the only identity path found that **rewrites** a value. Under D03-A it must refuse instead of trimming, so a ledger row and a claim can never disagree about the same account. Existing ledger values are already in the restricted domain, so no stored row changes.
- `uptime/correspondence.py:193` chooses the draft obligation-key shape with `scope.vendor.casefold() != "twilio"`. That is a vendor-name rule on the filing path. Under D04-C the shape comes from the governing family instead, and the Twilio case becomes one family entry rather than a name check.

Blocked work: the frozen dispute evaluation (corpus84 cases e86-01 and e86-04, `work/dispute-evaluation-86`) and any claim from an onboarded vendor whose source names contain spaces.

Fixed constraints for every option: preserve exact source bytes; never slug, trim, case-fold or rewrite a historical identity; keep technical route and artifact IDs restricted; keep old signatures, hashes and claim keys valid; missing evidence must stay distinguishable from "not applicable"; never invent a scope value.

## D03 — account and agreement identity

| | **D03-A: one bounded exact source-identity type** | **D03-B: explicit immutable identity mapping** | **D03-C: tighten onboarding to the restricted `Id` domain** |
|:---|:---|:---|:---|
| What changes | New shared `SourceIdentity` annotation replaces `Id` on `Scope.account`, `Scope.contract` and the account/agreement fields of `MonitorRow`, `MaintenanceRecord` and `IssuedCredit`. Onboarding overlays and `ramp_terms_store` use the same type. `claim_identity._identity` stays the key rule. | New `identity_binding` table: (tenant, kind, exact source bytes, source digest) → opaque internal ID. Claims carry internal IDs; screens show source text. Each binding is created by an explicit reviewed action. | Onboarding refuses names outside `Id`; operators enter slugs. |
| Accepted values | 1–96 characters; printable Unicode letters, digits, single ASCII spaces and `. , ' & ( ) + : / _ -`; no leading or trailing whitespace, no control characters, no tabs, no repeated spaces; must already be NFC. Anything else is **refused, not rewritten**. | Any onboarding-accepted value, mapped by review. | Current `Id` only. |
| Stored rows and keys | Stored **claim** identities passed the `Id` pattern, a subset of the new domain, so their keys, signatures and hashes should not change; a required property test confirms the subset. Stored **onboarding** values are unverified until an inventory runs. Any outside the new domain (for example a trailing space) get explicit remediation. | Legacy values bind to themselves, so old keys stay valid. New spaced values get generated IDs. Duplicate-filing risk across the boundary needs a dual lookup during migration. | Existing onboarded overlays with spaces lose their approvals and must be re-entered. |
| New authority | None | Who may bind two names to one customer or agreement. A wrong binding merges two parties' claims | None |
| Size | Small: one type, about eight field annotations, consumer joins, tests | Large: table, review action and UI, migration, authority policy | Small |
| Main risk | Visually identical names with different bytes form two identities, and a near-duplicate spelling can file twice. Mitigated by NFC-only, single-space, refuse-not-rewrite, plus an alias check that **warns** before filing. | Operator burden and a new high-impact authority surface | Violates "never slug"; loses the exact source identity the spec requires |
| Who prefers it | Reconciliation reviewer (handoff); handoff recommended default | Dispute owner (handoff) | Nobody; listed for completeness |

**Integration owner's preference (not a decision): D03-A now, with a blocking near-duplicate guard (added after the Opus critique), and D03-B kept as an additive later step** used only for equivalences a person declares. Strongest counterargument: D03-A lets two spellings of the same customer create two claim keys, which D03-B would prevent. Response: D03-B prevents that only when someone declares the alias. Without a declaration it adds the same risk plus a new authority. The pre-filing warning is cheap and keeps D03-B available.

## D04 — contract-specific claim scope

| | **D04-A: typed scope variants chosen by the client** | **D04-B: reviewed per-adapter scope binding in the manifest** | **D04-C: requirements derived server-side from the governing family** |
|:---|:---|:---|:---|
| What changes | `Scope` becomes a discriminated union: `service-month`, `resource-month`, `incident`, each with its own required fields. | Manifests declare `required_scope`, approved at promotion. Intake validates against it. | One `Scope` with typed optional component/incident/region/invoice. The server resolves the governing obligation family from (vendor, contract, service) and applies a fixed code table: required fields must be present, not-applicable fields must be absent, unknown family refuses. |
| Missing vs not applicable | Encoded by the variant | Encoded per adapter | Encoded by the family table. Invoice becomes evidence named by `INSUFFICIENT_EVIDENCE` when the fee basis needs it, not an intake key |
| Who chooses the shape | The client, so the server must verify the variant matches the governing family | The reviewer, at promotion | The server, from trusted terms; the client cannot pick a looser shape |
| Signed request bodies | New `kind` field; every client (web, scripts, evaluation harness) changes | Unchanged shape | Unchanged shape; optional fields may be omitted |
| Manifest bytes and approvals | Unchanged | **Changed.** Semantic digests move, so Northwind, CalyxQuay and Aster approvals are invalidated and must be re-reviewed | Unchanged |
| Stored claims | Read as the legacy full variant | Unchanged | Read as-is; strictness applies to new intake only |
| Claim keys | Unchanged; component, incident and region are not key inputs, and resource remedy already is | Unchanged | Unchanged |
| Main risk | Client picks the wrong variant; the extra check duplicates D04-C | Approval churn and a larger review burden for each adapter | Family table must be extended for each new family; an unknown family refuses until it is |

**Integration owner's preference (not a decision): D04-C.** It keeps signed bodies and manifest digests stable, and the trusted server, not the client, decides which fields apply. Strongest counterargument: the family table is code, so adding a family needs a code change, while D04-B lets a reviewer declare scope per adapter. Response: new families already need typed evaluator code (D05 boundary). A reviewer-declared scope with no matching evaluator would create an unsupported claim path.

## What each choice changes, file by file (for the implementation owner)

| File (owner) | D03-A | D03-B | D04-A | D04-C |
|:---|:---|:---|:---|:---|
| `uptime/correspondence_types.py` (W0) | Add `SourceIdentity`; re-annotate account/contract fields | Add internal-ID fields | Union of three scope models | Optional component/incident/region/invoice |
| `uptime/claim_identity.py` (W0) | None (key rule already matches) | Key from internal IDs plus legacy self-binding | None | None |
| `uptime/v4_routes.py` (W0) | Join on exact bytes (already) | Resolve bindings before joins | Verify variant against family | Apply family requirement table |
| `uptime/vendor_terms.py` overlay validation (W3) | Validate with `SourceIdentity` (refuse, not rewrite) | Create binding requests | None | None |
| `uptime/ramp_terms_store.py` (W1) | Use `SourceIdentity` | Use internal IDs | None | None |
| `uptime/allocations.py` `canonical` (W0) | Refuse instead of NFC plus strip | Map through bindings | None | None |
| `uptime/correspondence.py:193` (W4) | None | None | Variant replaces the vendor-name check | Family table replaces the vendor-name check |
| Web and script clients (W7/W8) | None | Show source text and bindings | Send `kind` | None |
| Evaluation harness 86 (paused) | Re-run e86-01/04 setup only after approval to resume | Same | Same | Same |

Existing tests that assert today's refusal of spaced identities, or that a full ten-field scope is required, would change under any option except D03-C. The identity specialist's ledger marks each one. Every such change must be listed by exact name in the test-change ledger; financial and authority assertions stay unchanged.

## Falsification tests to require whichever option is chosen

1. A claim for an onboarded vendor whose account and agreement contain spaces reaches the same economic key from both intake routes, and a retry files once.
2. Two different byte spellings of a name never silently merge. Under D03-A they get different keys plus a pre-filing warning; under D03-B they merge only through a recorded binding.
3. A trailing-space, control-character or non-NFC value is refused everywhere. No route accepts a value another refuses.
4. A whole-service monthly claim with no component, incident or region reaches evaluation. The same claim with an invented region is refused.
5. A resource claim with no invoice reaches evaluation and returns INSUFFICIENT_EVIDENCE naming the invoice. A missing resource ID is refused at intake.
6. Northwind January stays ELIGIBLE USD 2,400.00 and April stays USD 8,600; all existing claim keys and receipts are byte-identical.

## Rollback

D03-A and D04-C are schema-widening changes behind no flag. Reverting the commit restores refusal of new spaced or partial claims. Claims accepted in the meantime keep their stored bytes and keys, are listed, and are frozen for review rather than deleted. D03-B rollback must keep the binding table read-only for audit.

## Opus 5.5 critique

One genuine, tool-free critique: model `claude-opus-5-5`, session `83b1b59b-7fbe-42e5-84fe-f67986752dfc`, 2026-11-09T11:14:33Z. The sanitized [packet](../decisions/packets/94-identity-and-claim-scope-alternatives.md) contained no corpus cases, customer data or credentials. [Full reply](../decisions/reviews/94-identity-and-claim-scope-alternatives.json)

Opus also preferred D03-A and D04-C, with conditions. It **dissented** from leaving duplicate control to a later alias table. The table below records how each point is handled. These are changes to the proposal; the team still decides.

| Opus point | Disposition in this proposal |
|:---|:---|
| "Existing values are a subset, so no key changes" is unsupported: stored onboarding values may have trailing, repeated or non-NFC text | **Accepted.** Before implementation, an inventory of every stored account/agreement value against the new type is required. Pass condition: zero refusals, or a remediation list the team approves. Onboarded overlays that could never produce a key are already orphaned and get explicit remediation, not silent refusal. |
| A warning is advisory; case variants such as "Acme Ltd" and "ACME Ltd" can recover twice | **Accepted; preference changed.** D03-A now includes a **blocking** guard: a second filing for the same (tenant, folded vendor, agreement, month, remedy) whose account differs only by case or spacing is refused until a person records an override. That override is new authority and is part of the D03 decision. |
| Bring D03-B forward instead | **Not adopted, recorded as disagreement.** The blocking guard removes the double-recovery risk without creating a standing authority to merge parties. D03-B stays available if real aliases appear. |
| Ledger helper strips today, so ledger rows may differ from exact-byte keys | **Accepted.** Change it to refuse, then reconcile existing ledger rows against claim keys with sign-off. Known Northwind rows are already in the restricted domain. |
| Old signed claims may contain placeholder region/component values; "invented region refused" could change their re-evaluation | **Accepted.** Grandfather rule: stored claims are evaluated with their original scope and rules. The not-applicable-must-be-absent check applies to new intake only. |
| Absent vs null must not change canonical serialization | **Accepted** as a required test: old ten-field signed claims verify and evaluate byte-identically. |
| D04-C gaps: ambiguous family, vendor-name check, table versioning, scope defects shown as missing evidence | **Accepted.** Multiple matching families refuse. The `twilio` name check is removed. The family table is versioned and reviewed like evaluator code. Scope defects return a distinct invalid-scope refusal, never INSUFFICIENT_EVIDENCE. |
| Scale of the defect and frequency of new families are unknown | Agreed. The evidence is two authored claims plus one walkthrough; no frequency claim is made. |

Additional tests adopted: an identity inventory; a property test that the restricted `Id` domain is a subset of the new type; ledger/key reconciliation; a case-variant second filing is blocked; an ambiguous family is refused; old ten-field claims are byte-identical. Human authorization required: the team adopts D03/D04; claim-schema signers accept the intake type change; remediation of refused legacy identities, ledger reconciliation and any override authority are approved explicitly.

## Decision record

Owner: Ronok. Date: 2026-11-09. Ronok's choice reached three sessions, and all three records are kept here verbatim in substance:

| Source | What was recorded |
|:---|:---|
| Integration session (`agent0`), explicit options question | "D03-A + guard, D04-C (Recommended)": one exact source-identity type with a blocking near-duplicate guard; scope requirements derived server-side from the governing obligation family |
| Identity session (`agent1`), asked directly | D03-A with blocking guard and no override path; "D04-C: server table" |
| Overview session, relayed to the integration owner | D03 "Bounded exact source IDs" (alias/mapping registry not chosen); D04 "Typed scope variants": explicit scope types per obligation (whole-service month, resource period, incident-specific), with component, incident and region required only when the governing obligation needs them, "not applicable" distinct from "unknown", and nothing invented |

**Reconciled interface:** typed scope variants exist as explicit types, and the **server** selects the variant from the governing obligation family. The client does not declare a `kind`. That satisfies both the "typed scope variants" wording and the D04-C mechanism. If Ronok intended client-declared variants (D04-A, which changes every signed request body), this record must be amended before that part is implemented.

**Confirmed later on November 9:** answering the identity owner's evidence finding, Ronok chose "D04-C now, monthly keeps incident" (recorded in `agent1`'s session and relayed through the overview session). That confirms the server-selected interpretation above; no client-declared variant is being built. The monthly-availability family keeps requiring exactly one incident, because its evidence join reconciles coverage to `[scope.incident]` and takes minutes from one status interval. Whether a whole-service month can be proven without an incident is a separate, still-pending evidence-sufficiency decision.

**Dissent:** the dispute owner's recorded preference for explicit identity mappings (D03-B) was not chosen. Opus 5.5 dissented on deferring duplicate control; the blocking guard answers it. Override authority for the guard is a pending decision, so the guard blocks without an override.

