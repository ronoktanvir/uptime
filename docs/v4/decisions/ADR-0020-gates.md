# ADR-0020: Gates

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **BLOCKED — release evidence**.

## Decision and alternatives

Keep consequential local actions behind source-bound release evidence and keep independent onboarding/dispute work independent of Ramp write availability.

Old green tests alone miss new trust boundaries; enabling real actions during tests exceeds authority. Parallel synthetic gates avoid unnecessary serialization, but neither parallelism nor a digest proves independent witnessing.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/20-gates.json](reviews/20-gates.json); its sanitized input is [packets/20-gates.md](packets/20-gates.md). Receipt time: `2026-11-05T00:20:35.611287+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `f622a7b1-edd2-4cc5-be02-78b445607b9c`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus challenges self-attestation, shared-context independence and hash-as-secrecy. It requires outside-build attestations, provenance timing, authenticated actor classification and actual browser traces.

**Root position and reconciliation:** Accept the circularity objection. A local deployment interlock is useful but is not organizational approval, four completed gates, or human sign-off. Retaining V3 coverage must be demonstrated rather than inferred from a test count. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

gates.py requires security_financial, unseen_vendor, unanticipated_dispute and regression evidence matching the code manifest. The durable audit reports 116 executed observations passed but two browser observations UNAVAILABLE, baseline_verified=false and release_pass=false at dc092995.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/gates.py](../../../uptime/gates.py)
- [docs/v4/audit/RESULTS.md](../../../docs/v4/audit/RESULTS.md)
- [docs/v4/audit/main-release-v2.json](../../../docs/v4/audit/main-release-v2.json)

Audit: [durable audit results](../audit/RESULTS.md), especially its source pin, unavailable browser observations and failed release flags. This report does not certify the later inspected main revision.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_release_gate_v4.py tests/test_v4_audit_gate.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A changed money operand or source manifest passing its old gate, a scripted identity reported as human, or a missing browser observation counted as PASS falsifies release claims. Closing requires fresh pinned evidence for every required gate, reviewed by root.

## Versioned rollback

Remove/disable eligibility of stale release attestation without deleting historical evidence; restart observation-only. Preserve failed and raced reports and rerun against a frozen build before re-enabling local approvals. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `77dc2e2da43ecb940d271bb22021c29fc3cbc40bd91ac428d9a247bc8dae709f` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `b9b40148bba9e461eb628cb6979894ad17a02c0a14de9925c3f019f51c6cfc88`.
- Review-prompt SHA-256 recorded by receipt: `77129c09866f076bab55d23bc4d18b1677550ca7d633f4bbbdcc2abfad1ce374` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
