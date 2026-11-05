# ADR-0038: Durable restore and fail closed

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL — recovery documented; release blocked**.

## Decision and alternatives

Recover only identifiable durable artifacts, preserve unauditable historical claims as reports, and require fresh commit-pinned review/validation after restart.

Trusting summaries is cheap but circular. Recreating tests after seeing answers contaminates independence. Literal recovery plus fresh frozen evaluation costs time but can provide reproducible evidence when provenance survives.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/38-durable-restore-and-fail-closed.json](reviews/38-durable-restore-and-fail-closed.json); its sanitized input is [packets/38-durable-restore-and-fail-closed.md](packets/38-durable-restore-and-fail-closed.md). Receipt time: `2026-11-05T00:20:26.471182+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `984d65ef-9b59-4d99-8793-df34af54e4e2`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus says tool-history reconstruction is not proven literal without pre-restart hashes, and distinguishes commit-pinned fresh evidence from a narrative report. It requires new live grant checks before future effects.

**Root position and reconciliation:** Accept the provenance objection. These 28 actual receipt JSONs record fresh post-restart Opus sessions; they do not retroactively certify lost reviews. Historical V3 decisions 1–13 remain untouched. Root must assess the final integrated build rather than inherit worker or older audit claims. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

This ADR set verifies packet hashes against each receipt, model_requested/models, REVIEWED status, nonempty response and session. Main code was inspected at 1087804; audit main-release-v2 covers dc092995 and remains blocked on browser evidence. Neither is a final build attestation.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [docs/v4/audit/RESULTS.md](../../../docs/v4/audit/RESULTS.md)
- [docs/v4/audit/main-release-v2.json](../../../docs/v4/audit/main-release-v2.json)
- [docs/v4/audit/main-release-v2-raced.json](../../../docs/v4/audit/main-release-v2-raced.json)

Audit: [durable audit results](../audit/RESULTS.md), especially its source pin, unavailable browser observations and failed release flags. This report does not certify the later inspected main revision.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_v4_audit_protocol.py tests/test_release_gate_v4.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A reconstructed blob claimed original without surviving hash, a revealed input called blind, a raced source counted as stable, or an old receipt used for changed code falsifies restoration proof.

## Versioned rollback

Return to a known durable commit in an isolated checkout, leave later artifacts quarantined/history intact, and append a new recovery record. Never erase failed or raced receipts or manufacture missing witness evidence. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `a4495545ae9c43ce83ec4d8ba1c00d53a0ba8af7bcd77f4849e724264ffc3f86` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `25eb7248217972413c93fca20e8d2a374031cdda197a7770291b85c3dd1be824`.
- Review-prompt SHA-256 recorded by receipt: `bbbdfb09de4d76623a7a1eebaa72ac7067152d0a6ac8fe8190bb33547518b907` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
