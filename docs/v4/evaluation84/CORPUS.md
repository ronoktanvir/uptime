# Independent public evaluation84 corpus

This corpus contains six newly authored fictional contract sources and twelve newly authored vendor replies. Four contract sources target declared supported families; two contain material terms that require refusal. Six replies target supported semantic readings and six require review. The author was an independent GPT-family Codex subagent assigned high-reasoning work. No human verification, real customer outcome, private blind performance, or general vendor-population coverage is claimed.

Source text, customer evidence and independent expected results are separate. Only contract `document.json` text is an onboarding model input. Customer evidence is fictional but is held locally in `customer.json`; it must not enter contract extraction prompts. Dispute `source.json` contains the reply and explicit relevant context. Its `claim_basis` identifies the original independently authored contract and customer scenario, so a runner can derive the original claim through the normal deterministic path. Paths and independently held gold are not model inputs. Replies describe independent case snapshots; they must not be summed as separate economic obligations.

## Input contract

- `onboarding/<id>/document.json`: `name`, `uri`, `classification`, `text`.
- `onboarding/<id>/customer.json`: `classification`, `overlay`, `scenarios` containing `name` and `facts`. Two scenarios accompany each positive contract. The two monthly contracts also include `governing_fee_source`: an independently authored fixed-fee order, explicit pricing facts and signature time, an itemized invoice with service endpoints/quantity/net fee/zero tax/issue and observation times, and a scripted custody statement. These are source facts for mechanical registration through the normal pricing/billing path, not an opaque authority object or an assertion of real signature or human review. Unsupported controls do not invent a usable customer calculation.
- `disputes/<id>/source.json`: `id`, `vendor`, `reply`, `context`. Context contains the original claim scope, exact currency/amount, referenced contract/customer scenario, receipt facts, described artifacts and sender attribution. Context amounts are factual original-claim inputs; expected reply meaning remains separate.
- `manifest.json`: each input file's SHA-256 and byte length, each sealed expected file's SHA-256, and declared family/profile routing.

`monthly_tier`, `completed_step`, `unsupported_variable_fee` and `ambiguous_deadline` use `monthly-propositions`. `resource_month` and `aggregate_fixed_month` use `resource-month`. These are author-supplied family choices, not evidence of autonomous family discovery. Future invoice credits, service credits, awards and applied money remain distinct stages.

## Independent oracle and freeze

The expected files are outside Git under the owner-only directory recorded in the manifest. They include hand-derived outcomes and exact monetary amounts, the semantic reason and required stage for each refusal/review control, and comparison rules. The source commit and manifest hashes freeze both public input and sealed gold before any runtime result or model inference is observed. Neither implementers nor the integration lead should read gold until all first attempts are terminal. No prior source case, gold file, parser implementation, test fixture or model output was inspected to author these inputs. The allowed public documentation contains illustrative material, but its prose, vendors, figures and periods were not copied into this corpus.

Scoring must separate successful positive extraction, deterministic financial correctness, semantic meaning, safe refusal and authority preservation. A safe refusal of an intended positive contract is a coverage failure. A review control is successful only when its actual unsupported meaning is preserved and no operational assertion or action is manufactured. A model failure, transport failure and missing runtime prerequisite must be reported at their actual stages. Preserve first attempts; any later correction is a separately named remediation, not a replacement score.

Expected cents permit only exact decimal normalization; no numeric tolerance. Categories and references must preserve meaning and exact identity. Taxonomy spelling may differ only under an explicit one-to-one meaning-preserving map. Unknown money stays unknown. The independent sealed comparison rules provide the complete scoring contract. A subsequently discovered oracle defect requires a separate immutable adjudication; original source and gold bytes remain unchanged.

## Evidence consulted

The author read only these repository instructions/specifications/public semantic or interface documents:

1. `AGENTS.md`.
2. `docs/uptime-v3/AGENTS.md`.
3. `docs/uptime-v3/Uptime_V3_Orchestrator_Handoff.md`.
4. `docs/uptime-v3/Uptime_V3_Product_Technical_Spec.md`.
5. `docs/uptime-v3/Uptime_V3_Work_DAG.md`.
6. `docs/uptime-v3/Uptime_V3_Credentials.md` (setup instructions only; no credential file accessed).
7. `docs/vendor-onboarding.md`.
8. `docs/v4/decisions/ADR-0025-open-contract-propositions.md`.
9. `docs/v4/decisions/ADR-0028-resource-month-evidence.md`.
10. `docs/v4/decisions/ADR-0077-source-bound-resource-periods.md`.
11. `docs/v4/decisions/ADR-0079-monthly-profile-and-offline-export.md`.

The lead additionally supplied the interface fact that completed steps are a mutually exclusive monthly-tier `credit_rule`, with exact percentages, integer floor and final HALF_UP rounding. The lead supplied semantic requirements for independent fixed-fee source and invoice evidence; the onboarding harness owner clarified that aggregate overlays omit `resource_id`, and that monthly pricing authority must arise through normal local pricing/billing registration, not a caller-created authority flag. No implementation source, prior fixture, review transcript, extraction proposal, private holdout or inference output was opened. The repository's broad review/delegation instructions were narrowed by this assignment: the lead owns the actual Opus criticism and inference authorization, and this author runs no separate council or model call.
