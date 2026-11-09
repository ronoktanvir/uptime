# V4 decision records: 14–41

Recorded 2026-11-04T16:58:23-08:00. These 28 ADRs preserve the root packets, actual independent Claude Opus 5.5 responses, alternatives, dissent, bounded implementation findings, falsifiers and versioned rollback. **They do not certify a final release or four passed gates.** Historical V3 records 1–13 under `docs/decisions/` are unchanged.

Canonical packet/review files remain in the durable main release at `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`. Relative links in the ADRs resolve after integration beside those files; no copies or edits of packets/reviews were made in this worktree. All 28 receipts have status REVIEWED, a nonempty response/session, requested and confirmed `claude-opus-5-5`, and matching packet SHA-256. Each ADR also pins the actual JSON bytes. Receipt timestamps are November 5 UTC, which is November 4 in America/Los_Angeles; numbering is decision identity, not chronological call order. These were live reviews re-performed after restart, not recovered V3 reviews.

The code assessment is pinned to main `1087804986151624f395e9ea1c929c16ede6944d`. Worker-only/staged code is identified separately, especially decisions 32, 40 and 41. PARTIAL means a decision has some code/evidence but its listed boundary or validation remains unproven; PROPOSED means it is not established in that main build; BLOCKED identifies the exact unavailable outcome. SUPERSEDED preserves a rejected approach. None means commercial authorization. Root packet positions and this ADR owner's evidence-based reconciliation are explicitly distinguished from root's pending final build review.

| ADR | Decision | Status |
| --- | --- | --- |
| [14](ADR-0014-auth.md) | Auth | PARTIAL |
| [15](ADR-0015-finance.md) | Finance | PARTIAL |
| [16](ADR-0016-allocation.md) | Allocation | PARTIAL |
| [17](ADR-0017-onboarding.md) | Onboarding | PARTIAL |
| [18](ADR-0018-correspondence.md) | Correspondence | PARTIAL |
| [19](ADR-0019-ramp.md) | Ramp | BLOCKED — native writes |
| [20](ADR-0020-gates.md) | Gates | BLOCKED — release evidence |
| [21](ADR-0021-registry-ledger.md) | Registry ledger | PARTIAL |
| [22](ADR-0022-sender-authority.md) | Sender authority | SUPERSEDED — reviewer HMAC; residual risks remain |
| [23](ADR-0023-local-source-intake.md) | Local source intake | PARTIAL — refined by ADR-0029 |
| [24](ADR-0024-cross-route-claim-identity.md) | Cross route claim identity | PARTIAL |
| [25](ADR-0025-open-contract-propositions.md) | Open contract propositions | PARTIAL |
| [26](ADR-0026-public-key-reviewers.md) | Public key reviewers | PARTIAL |
| [27](ADR-0027-active-remedy-join.md) | Active remedy join | PARTIAL |
| [28](ADR-0028-resource-month-evidence.md) | Resource month evidence | PARTIAL |
| [29](ADR-0029-source-key-grants.md) | Source key grants | PARTIAL |
| [30](ADR-0030-tenant-reviewer-mandates.md) | Tenant reviewer mandates | PARTIAL |
| [31](ADR-0031-ramp-system-of-record.md) | Ramp system of record | PARTIAL — reads observed; write enforcement unproven |
| [32](ADR-0032-ramp-workflow-surface.md) | Ramp workflow surface | PARTIAL — local adapter; native delivery blocked |
| [33](ADR-0033-ramp-inbound-security.md) | Ramp inbound security | PARTIAL — hex correction; registration blocked |
| [34](ADR-0034-ramp-credit-attribution.md) | Ramp credit attribution | PARTIAL — bounded attribution only |
| [35](ADR-0035-ramp-authorization-and-demo.md) | Ramp authorization and demo | BLOCKED — customer install and native write proof |
| [36](ADR-0036-explicit-invoice-total-cap.md) | Explicit invoice total cap | PARTIAL — constructed rehearsal only |
| [37](ADR-0037-evaluator-version-pin.md) | Evaluator version pin | PARTIAL — stronger pin implemented |
| [38](ADR-0038-durable-restore-and-fail-closed.md) | Durable restore and fail closed | PARTIAL — recovery documented; release blocked |
| [39](ADR-0039-supplements-conditional-windows-and-offsets.md) | Supplements conditional windows and offsets | PARTIAL — bounded operators; generalization unproven |
| [40](ADR-0040-provider-confirmed-awards.md) | Provider confirmed awards | PROPOSED — staged companion; not integrated proof |
| [41](ADR-0041-operable-terms-binding.md) | Operable terms binding | PARTIAL — binding path proposed; workbench unbound |

## Disagreements that control interpretation

- 22 → 26: reject password-derived reviewer HMAC; public keys reduce verifier exposure but do not solve XSS, private-key theft or OS compromise. WebAuthn is a real alternative, including in CI.
- 24: omit agreement version from monthly business identity; version provenance does not create a new filing right.
- 27: preserve verified negotiated amendments as a possible override, dissenting from an absolute “overlay can only narrow” rule; unverified widening refuses.
- 28 and 39: repaired revealed examples are regression evidence, not fresh blind generalization.
- 31 and 35: reported OAuth grant omission is not an observed HTTP write rejection and does not diagnose administrator settings.
- 33: the original packet's base64 premise is wrong; implemented verification uses hex HMAC-SHA256 over exact raw bytes. The historical packet remains unchanged.
- 34 and 40: reciprocal Ramp resources are one system, not independent vendor award confirmation. Bounded one-award-per-credit binding is not generalized N:M. Observed Ramp application is not cash.
- 36: USD800 was chosen knowing USD840; USD40 is a constructed hypothetical discrepancy, not blind detection or demonstrated savings.
- 17, 26, 30 and 41: an authenticated sandbox operator/key does not prove actual human activation, organizational mandate or authentic commercial terms.
- 37: bounded source hashes implement a stronger pin than self-declared semantic versions, with conservative reapproval cost.
- 41: the workbench is unbound at the inspected main revision; a typed evaluator alone is not operable authorized contract intake.

## Validation and handoff

The ADR owner read every packet and full response JSON for 14–41, compared selected code paths against the pinned main release and identified worker-only evidence. No heldout data, external calls, credential values or customer documents were accessed. The durable audit `docs/v4/audit/main-release-v2.json` covers `dc0929957075d0f7392283a705b876c28cd343d8`, not the later main pin: 116 executed observations passed, two real-browser observations were UNAVAILABLE, and baseline_verified/release_pass were false. The raced report remains failed evidence. Do not promote its counts into a final release claim.

ADR-owner executed check on branch `remediate/adr`, application base `8393fc5ef57cf1bb1e1df055b281f79e4ce338bd`, November 4 local / November 5 UTC:

```sh
UV_OFFLINE=1 UV_CACHE_DIR=/private/tmp/uptime-adr-uv-cache uv run --locked pytest tests/test_financial_v4.py tests/test_allocation_ledger.py tests/test_claim_identity.py tests/test_case_revision_v4.py tests/test_v4_authority.py -q
```

Result: **116 passed, 1 warning in 12.26s**, exit 0. The warning was the existing Starlette/httpx deprecation; uv also warned it could not acquire an environment lock. This is bounded synthetic/offline regression on the ADR worktree's older application base, not a rerun of the main-release audit and not a final-build test result.

Documentation checks: exactly ADR-0014 through ADR-0041, no duplicate numbers, required decision/review/evidence/falsifier/rollback sections, matching packet and JSON hashes, and valid main-release-relative evidence targets. `git diff --check` passed. Only these 28 Markdown ADRs and this index are included in the commit. Per-ADR commands are focused reproduction requirements, not assertions of current execution. No merge was performed by this owner. Root must integrate the documentation, run the required `uv run --locked pytest` after each merge, review all stated dissent/statuses against the final frozen source, and update final build evidence. Application code, historical V3 records and canonical packet/review bytes remain outside this change.

## Subsequent integrated decisions

The earlier table preserves its inspected-source status. The following decisions and engineering status record later integrations.

- [42 — Substantive release evidence and independent review](ADR-0042-release-authority-and-independent-critique.md)
- [43 — A usable, redacted native bill finding](ADR-0043-native-review-message.md)
- [44 — Reusable contractual evidence primitives](ADR-0044-temporal-coverage-evidence-and-filing.md)
- [45 — Local draft intake without approval authority](ADR-0045-local-draft-staging.md)
- [46 — Independent implementation critique](ADR-0046-integrated-code-critique.md)
- [47 — Exact native vendor associations](ADR-0047-linked-vendor-context.md)
- [48 — Immutable original filing source pins](ADR-0048-original-filing-terms-pin.md)
- [49 — Economic cardinality and compound denials](ADR-0049-economic-cardinality-and-compound-denials.md)
- [50 — Legacy delimiter collision containment](ADR-0050-ambiguous-resource-identifiers.md)
- [51 — Private GitHub engineering repository](ADR-0051-private-github-repository.md)
- [52 — Signed source references for filing fields](ADR-0052-grounded-filing-references.md)
- [53 — Local engineering dependency dashboard](ADR-0053-read-only-progress-dashboard.md)
- [54 — Signed plan references within the filing join](ADR-0054-signed-plan-reference-completion.md)
- [55 — Onboarding operator consistency and public diagnostics](ADR-0055-onboarding-operator-consistency.md)
- [56 — Bounded vendor-response coverage](ADR-0056-bounded-vendor-response-coverage.md)
- [57 — Bind the visible Ramp demo to its own installation](ADR-0057-native-demo-installation-identity.md)
- [58 — Bounded source-label whitespace equivalence](ADR-0058-bounded-source-label-whitespace.md)
- [60 — Source-locked interpretation and independent authority](../OPUS60-INTERPRETATION-RECOMMENDATION.md)
- [61 — Explicit source meaning before monetary evaluation](ADR-0061-source-semantic-bindings.md)
- [62 — Public model transport, measured refusals and limitations](../DECISION62-PUBLIC-TRANSPORT.md)
- [64 — A coherent financial walkthrough with ordinary product views](ADR-0064-clean-walkthrough.md)
- [67 — Current financial projections and contradictory source meanings](ADR-0067-current-semantic-containment.md)
- [68 — Honest application to the next regular invoice](ADR-0068-future-invoice-application.md)

Current implementation and test boundaries appear in [engineering status](../STATUS.md). Publishing the private GitHub repository preserves the original source-linked decisions and independent findings.

- [87 — Person-operated demo and preserved authority](ADR-0087-person-operated-demo-path.md)
- [94 — Account identity and claim scope (D03-A, D04-C), alternatives and one Opus critique](../integration90/D03-D04-ALTERNATIVES.md) · [packet](packets/94-identity-and-claim-scope-alternatives.md) · [review](reviews/94-identity-and-claim-scope-alternatives.json)
- [90 — Read-only adapter requirement card](ADR-0090-adapter-requirement-card.md)
- [91 — Refuse out-of-period evidence at the signed source grant](ADR-0091-evidence-temporal-applicability.md)
- [93 — One Ramp case identity from financial record to reconciliation](ADR-0093-ramp-case-lineage.md)
- [96 — Workspace recovery, installation revocation and operations health](ADR-0096-operations-recovery.md)
- [89 — Reviewed denial acceptance and dispute trace](ADR-0089-reviewed-denial-acceptance.md)
- [95 — Grounded read-only finance guide and next steps](ADR-0095-grounded-finance-guide.md)
- [Team decisions of 2026-11-09 (owner Ronok): D03 bounded exact source IDs, D04 server-selected scope variants, D05 auto-select plus human approval, D06 humans gate judgment, D07 narrow published matrix, D11 stay local](../TEAM-DECISION-HANDOFF.md#team-decision-sheet)
- [91a — Twilio public status page as the first real evidence source](ADR-0091a-public-status-source.md)
- [97 — Automatic rule-family selection (D05 phase 1)](ADR-0097-automatic-family-selection.md)
- [Ronok's 2a — closure-bound accept-denial mandate](../integration90/D06-ACTION-MATRIX.md)
