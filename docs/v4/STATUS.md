# Uptime V4 engineering status

The application now treats Ramp as the financial system of record and Uptime as its contract, evidence and dispute companion. Native bill and credit identifiers anchor the worklist. Live publication in Ramp is still blocked by missing write grants. The local engine, signed review paths and simulated end-to-end flows remain under final integration verification.

## Verified live integration

The November 5 UTC refresh installed capture `2265946dc34c21ecbf84daa536db765f1a237cebf32857c943fdf0a3786756ff` into the actual local sandbox workspace. Six bills were read by native ID. All five distinct vendors referenced by those bills were fetched and matched by exact ID. The shared detail budget also read seven additional vendor records. The broader sample contains twelve transactions, twelve purchase orders and eleven approval observations. Vendor, transaction and purchase-order inventories remain explicitly truncated. Agreement and vendor-credit lists completed with zero records.

The OAuth exchanges still omit `bills:write`. These observations establish a missing grant. They cannot isolate the developer app's allowed-scope setting from entitlement restrictions. The available Ramp sandbox browser remains at sign-in, so administrator configuration is unverified. No live comment, draft bill, payment action, award or credit application has been sent. Current public interfaces and exact setup requirements appear in [the supported-integration analysis](RAMP-FEASIBILITY.md).

## Implemented work

- Ramp capture and normal application readback associate bills, vendor records, transactions, purchase orders, approvals and available credits. Coverage, freshness and original capture provenance remain visible.
- Signed contract bindings and the deterministic evaluator can evaluate supported contractual terms against native records with sufficient evidence. The actual observed bills lack usable agreement and line-level pricing evidence. The USD840 bill with a constructed USD800 cap demonstrates a separate hypothetical USD40 discrepancy.
- The native workflow implements exact-object preparation, review, final authorization, durable dispatch and same-thread comment readback. Blank Canvas processing verifies signed trigger and reset state and keeps procurement identifiers distinct from bill IDs. Live configuration remains required.
- Generic declarative onboarding supports bounded monthly and resource/service-month contract families, source quotation checks, independent tests, customer overlays, shadow evaluation, interpretation review, approval, activation and rollback. Real Opus proposals and rejected attempts are retained. Scripted review identities in tests carry explicit simulation labels.
- Signed correspondence intake supports independently supplied vendor text and evidence, bounded evidence requests and rebuttals, correct denials, ambiguity escalation, original receipt linkage, and approved procedural supplements. External vendor delivery remains separately authorized.
- Credit reconciliation separates estimated eligibility, filed claims, verified vendor awards, native credit observations, recorded balances and bill applications. ACTUAL attribution requires independent original-filing and award witnesses, exact native records and immutable original terms/source pins. The actual installed database contains zero awards, applications and correspondence claims.
- The workbench provides the Ramp financial worklist plus advanced evidence, vendor onboarding, dispute and audit views. Its local launcher enrolls a view-only identity. The scoped reviewer draft lane permits inspection while consequential gates remain closed.

The [capability matrix](CAPABILITIES.md) and [remaining engineering gaps](REMAINING-RISK.md) explain each boundary. The [operations guide](OPERATIONS.md) contains setup, local roles, restart, refresh and deployment requirements.

## Audit evidence and active verification

The initial V3 before/after campaign contains118 assertions. V3 passed73 and failed45. Root verified commit `38bca3e` from a detached source-stable checkout. All2,187 Python tests,34 JavaScript tests and118 independent audit assertions passed, including actual browser and socket checks. The separate progress-graph tests also passed. GitHub workflow41963124265 passed the same source with full checkout history and required browser/server execution. The earlier `b6666b4` result remains separately recorded. Each later application change requires its own verification.

The independent high-reasoning coding reviewer reproduced four additional defects while145 existing tests passed. They affected attribution after a lawful reply, aggregation across distinct resources, regional claim identity, and compound denials containing an unknown waiver assertion. The original [review and reproductions](INDEPENDENT-FINAL-REVIEW.md) remain intact. Corrective commits were integrated. A separate independent verifier passed the corrected lifecycles, including persistence, later award attribution and tamper refusal. Root repeated that verification after the delimiter-collision guard. The [independent verification](INDEPENDENT-FINAL-FIX-VERIFICATION.md) records its exact source and scope.

Earlier workstream runs recorded a request-classification regression, ambiguous delimiter risk and38 setup timeouts during the cloud filesystem stall. The corrections and clean source-stable runs are now recorded. Historical failures remain in the checkpoint log.

Independent private evaluation campaigns preserve their original denominators and failed attempts. A real-socket replay on `f56e067` completed2/10 original cases and1/8 additive cases. The additive arithmetic succeeded8/8, while denial dispositions remained0/7. An independent coding review traced every additive workflow failure to the remaining `plan` reference mismatch. Earlier service and fee corrections did not resolve that field. The original cohort also contains missing historical filing evidence. The [socket diagnosis](INDEPENDENT-SOCKET-DIAGNOSIS.md) separates those causes and retains all denominators. Correction and a new immutable replay are in progress.

The third independently chosen public document remains refused. Review found an extraction-hint whitespace inconsistency and a correctly rejected unsupported verification-authority proposition. Onboarding remediation proceeds separately from disputes. Supported public contracts and studied-case improvements establish their measured families. Broader unseen-vendor performance and actual human promotion remain pending.

The private [GitHub repository](https://github.com/ronoktanvir/uptime) preserves the existing commit history. Reachable-history scans and a fresh remote clone verified publication. The [local engineering dashboard](http://127.0.0.1:8780/) exposes a dated dependency map with source-bound evidence, blockers and owners. Its snapshot is maintained after verification.

## Immediate priorities

1. Correct the independently reproduced plan-reference mismatch, repeat the unchanged private cohorts, and rerun financial/security verification on the resulting source.
2. Complete the bounded onboarding hint and authority-diagnostic corrections while preserving the original rejected proposals and independent results. Continue focused GitHub commits and source-bound CI.
3. Obtain the administrator's configured sandbox write grant, then run an exact reviewed comment or safe draft action and its same-object readback. Blank Canvas additionally requires the actual configured workflow step and webhook receiver.
4. Supply authentic customer terms and necessary usage/fee evidence before interpreting a live native record as a contractual claim. Obtain actual human review before adapter activation or external correspondence.

Onboarding and adversarial disputes remain parallel high-priority workstreams. Additional supported grammar, new independent cases and deployment operations remain explicit engineering work. The current release lacks a production-readiness certification.

## Durable execution

The active Git directory was moved outside cloud-synchronized Documents after observed dataless Git objects and duplicate invalid ref filenames caused multi-minute stalls. The original directory is preserved. The existing project path and workspace shortcut resolve to the verified local copy. Git integrity checks passed. Private fixtures, credentials and runtime databases remain outside the repository. The finance application was restarted on verified source and its existing view-only account successfully opened the installed Ramp capture. The progress server runs separately on port8780. Processes run only while the current environment remains available, with a reproducible restart procedure in the operations guide.

