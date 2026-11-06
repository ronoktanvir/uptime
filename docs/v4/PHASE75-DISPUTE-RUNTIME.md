# Dispute interpretation in the product

Workstream 75 implements decision 73's operator-approved public proposal runtime through the existing unfamiliar-vendor-wording page. A new authenticated case response can produce a model proposal after the exact full outbound request is approved offline; no scenario or vendor branch is required. The request label and source label grant no authority by themselves.

## User and operator flow

1. Open the existing correspondence case and choose **Review unfamiliar vendor wording**. The complete signed source and exact source blocks remain visible.
2. Record an independent reading. Model output remains withheld until that actor saves their own reading.
3. Expand **Interpretation request permission → Complete request for operator approval**. Its export contains exactly `tenant`, `subject`, `kind`, `target`, `context_sha256`, `request`, and `source_references`. The request includes the pinned provider profile, prompt, schema, public source text and initial attempt nonce. An operator uses the offline approval tool; this page cannot grant permission.
4. Refresh request permission, then choose **Request interpretation**. The POST persists a job and returns; provider I/O runs outside the HTTP mutation lock. The page shows queued, running and terminal status with bounded polling and manual refresh. Duplicate submission returns the existing job; cancelled or uncertain work is not silently retried.
5. Compare the proposed meaning against exact original quotes, selected slot/condition locations and the request reference. No acceptance decision or review attestation is preselected. Multiple propositions are not flattened automatically into the current single-main-assertion form.
6. Reconcile the meaning, attest source coverage and inspect the deterministic preview. Only existing evidence-backed preparation rules apply. A reported award remains informational and cannot book money. A prepared response still requires the existing exact approval before submission.

Root owns startup/configuration wiring through `inbox.public_proposal_jobs`, plus the offline approval tool and core service. This workstream owns the domain wrapper, atomic context/reading checks, API routes, source display and review UI. The standalone public adapter's serialized request bytes, schema and prompt remain unchanged; runtime adds only `attempt_nonce: "initial"` and requires a separately approved complete request. No retry UI is provided.

## Evidence and limits

Actual Claude Code Opus 5.5 implemented the wrapper, routes, parser helper, review hooks, UI and tests in session `6cd955be-2fa5-4b85-96aa-4b8de46982a4`, completing successfully in 598.4 seconds. Its inventory was exactly Edit/Glob/Grep/Read/Write with no MCP servers or denied calls. The [coding receipt](decisions/reviews/75-dispute-runtime-coding.json) records the exact stream hash and parent corrections. It implemented the already reviewed decision 73; no second review council ran.

The fresh authored public response was frozen in `e23f7bc` before live inference. The [actual runtime proof](evidence/dispute-runtime-75-public-queue.json) shows an unapproved request refused with 403 and no provider call, followed by a normal owner-only exact-request approval and one successful actual Opus job. The case stayed unchanged when the candidate arrived. Scripted explicit semantic review produced a time-bar preview, prepared an unapproved response draft with unchanged ledger, and submission without the existing exact approval returned 409. This exercises the full product API path; scripted review is not actual human-review evidence.

Candidate insertion and its current-context check are atomic within the correspondence transaction. Job completion is a separate commit. A crash between them may leave an inert candidate attached while the job becomes UNCERTAIN; the candidate and job share the request hash, the UI acknowledges that possibility, and no retry or action authority follows. The regression preserves this limitation rather than claiming cross-system atomicity.

Earlier authored batches and independent qualification scores remain unchanged. This single runtime proof does not establish unseen semantic generalization. Customer model processing stays disabled unless a different authorized capability is deliberately designed; the only available runtime path here is an operator's exact public-request allowlist.

Focused validation and source-pinned verification are recorded in [TEST-CHANGES-75.md](TEST-CHANGES-75.md). Root runs the full suite after integration. Rollback removes the additive job wrapper/routes/configuration and restores the prior UI; the original signed sources, financial engines, reviewed interpretations and failed/uncertain job evidence are preserved.
