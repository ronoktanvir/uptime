# ADR-0036: Explicit invoice total cap

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL — constructed rehearsal only**.

## Decision and alternatives

Use an explicitly synthetic USD800 total-invoice cap against the observed USD840 sandbox bill solely as a constructed USD40 plumbing rehearsal.

Unit-price evaluation needs absent quantities/rates; inventing them fabricates provider facts. Fully synthetic fixtures are reproducible but lack fetched-record context. Waiting for genuine terms is commercially credible but leaves this rehearsal blocked; a precommitted negative-control design would be stronger detection evidence.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/36-explicit-invoice-total-cap.json](reviews/36-explicit-invoice-total-cap.json); its sanitized input is [packets/36-explicit-invoice-total-cap.md](packets/36-explicit-invoice-total-cap.md). Receipt time: `2026-11-05T00:20:16.805544+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `c7f0e950-e04e-4798-941c-4b2d5c2977cc`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus rejects “independently selected” because root knew the bill total. It says the example demonstrates wiring, not discovery, and asks about total semantics, signing authority, snapshot drift and negative controls.

**Root position and reconciliation:** Accept the dissent explicitly: the USD800 cap was chosen with knowledge of USD840. Neither independence nor blind detection is established. The hypothetical difference is USD40; there is no demonstrated prevention/recovery. Preserve null actual-recovery fields rather than converting unknown to a realized zero or cash claim. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

ramp_cap binds exact bill/capture/terms and marks publishable=false; constructed-cap.json records CONSTRUCTED_REHEARSAL and amount 40.00 with actual_recovery=null. This does not establish a real negotiated agreement.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/ramp_cap.py](../../../uptime/ramp_cap.py)
- [uptime/ramp_workspace.py](../../../uptime/ramp_workspace.py)
- [docs/v4/evidence/constructed-cap.json](../../../docs/v4/evidence/constructed-cap.json)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_ramp_cap_v4.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Cap at/above total producing a positive discrepancy, changed bill snapshot remaining valid, tax-exclusive semantics treated as total-inclusive, currency mismatch or duplicate binding accepted falsifies the rehearsal. Genuine contract detection needs independently evidenced governing terms.

## Versioned rollback

Remove the constructed overlay from active display and preserve its signed payload/receipt as historical rehearsal. Restore compatible cap evaluator only; no provider bill modification or financial reversal is implied. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `ab2af31943ee28849c5e1dd602fd942254c63b5ef0d24b888521a77bda8fb64c` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `b8b3f5dc8ace0b0b13e6eec5f604c26cc7368bc1bd82a9b127974a83e2b26bab`.
- Review-prompt SHA-256 recorded by receipt: `050fc67c2fe592ad0567ed161f39f88fbe3326c145c62eb6f1a02fc095b05a73` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
