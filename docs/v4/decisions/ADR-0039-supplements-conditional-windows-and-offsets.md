# ADR-0039: Supplements conditional windows and offsets

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL — bounded operators; generalization unproven**.

## Decision and alternatives

Add only source-bound declarative operators for qualified maintenance, interval union, net resource fees, unchanged supplement deadlines and prior-credit offsets; missing operands remain unknown.

LLM adjudication makes money nondeterministic; ignoring clauses creates false positives; bespoke hand-authored vendor adapters hide generalization limits. General operators cost interpreter complexity, evidence collection and independent regression.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/39-supplements-conditional-windows-and-offsets.json](reviews/39-supplements-conditional-windows-and-offsets.json); its sanitized input is [packets/39-supplements-conditional-windows-and-offsets.md](packets/39-supplements-conditional-windows-and-offsets.md). Receipt time: `2026-11-05T00:27:36.529720+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `c256cc9c-328d-456f-ab96-cb49edc4640b`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus endorses quarantine and explicit semantics but warns of overfitting to a revealed synthetic source. It distinguishes attested zero from missing prior-award evidence and requires same-clock supplements, partial maintenance intersection and post-discount fee scope.

**Root position and reconciliation:** Accept those semantics and the overfitting objection. A prior award is not a Ramp payment. Newly implemented operators can close an engineering gap without proving a fresh unseen test; retain refusal history and require independently frozen retesting. No heldout source or oracle was read for these ADRs. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

vendor_resource_operators defines finite maintenance, interval_measurement, fee_adjustment, supplement and prior_credit operators. Resource evaluation separately checks prior-credit facts, maintenance windows, fractional intervals and filing proof; correspondence assembles complete source reports.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/vendor_resource_operators.py](../../../uptime/vendor_resource_operators.py)
- [uptime/vendor_resource_eval.py](../../../uptime/vendor_resource_eval.py)
- [uptime/correspondence_resource.py](../../../uptime/correspondence_resource.py)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_vendor_resource_operators.py tests/test_correspondence_resource.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Missing prior-award evidence treated as zero, whole outage exempted by partial maintenance overlap, duplicate interval double-counted, fees outside clause scope included, or a denial/supplement resetting the clock falsifies the operators.

## Versioned rollback

Revoke the affected source/profile revision, retain immutable operator/source hashes and receipts, and append reevaluation diffs. A restored compatible version still needs its prior valid approval; a changed meaning needs fresh review. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `c40f11fa7ba5b138af1e6ace6aa4bc466c97a0804da1c631bc81fee71f198a0e` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `eae0ebb506301c1b5856171f2b8c2db060574567c22d1447f922a174d0e45c7c`.
- Review-prompt SHA-256 recorded by receipt: `2db039b8f84d149ad0e361dbb20b85260ac7ec1e229e8ab2396b3b4219ec4923` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
