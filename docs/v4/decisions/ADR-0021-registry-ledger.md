# ADR-0021: Registry ledger

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Append content-addressed case revisions and derive typed stage/cohort totals from unique ledger identities, preserving historical snapshots.

Mutable overwrite loses explanation history; title-based/hardcoded case selection fails for new cases. Full event sourcing or bitemporal storage provides richer replay at higher complexity than append-only snapshots.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/21-registry-ledger.json](reviews/21-registry-ledger.json); its sanitized input is [packets/21-registry-ledger.md](packets/21-registry-ledger.md). Receipt time: `2026-11-05T00:20:40.319514+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `7458df14-4bfd-4f99-8ea9-6f5a732e463b`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus supports revisions and typed filters but warns that a mutable current pointer can race, cohorts can double-count receipts, and mixed currencies or malformed statuses can mislead.

**Root position and reconciliation:** Accept the atomicity concern; actual storage selects latest ordered revisions rather than adopting an unchecked mutable pointer. Distinguish entered cases from seeded comparisons, and keep unknown recovery unknown. Packet examples motivate tests, not causal proof by themselves. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

storage.persist_case appends changed payloads in the caller transaction; identical payloads reuse the head. case_revision UPDATE/DELETE triggers preserve history. Audit records the paid-title failure at an older candidate and its passing observation on dc092995.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/storage.py](../../../uptime/storage.py)
- [uptime/workbench.py](../../../uptime/workbench.py)
- [docs/v4/audit/RESULTS.md](../../../docs/v4/audit/RESULTS.md)

Audit: [durable audit results](../audit/RESULTS.md), especially its source pin, unavailable browser observations and failed release flags. This report does not certify the later inspected main revision.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_case_revision_v4.py tests/test_portfolio_v4.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Identical input adding monetary value, a seeded comparison entering customer ROI, orphaned/lost concurrent revisions, or malformed payment state becoming PAID falsifies the projection.

## Versioned rollback

Disable the derived projection and recompute from retained immutable history with a pinned projector. Revert code without deleting revisions or rewriting V3 revision-one snapshots. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `a099fca47e7ae9e8ef811eaf07a288531f0358a04beb5ee5c0dbb73dcca2e4cf` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `ccc3d55eeffc68c10e128885c0271b4cf62e500bdd5222f4f7200ecabc69d39e`.
- Review-prompt SHA-256 recorded by receipt: `fc5e14cb876758f882eadf21029c54fe68a3b74dccbda48a2d591630c1acb89c` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
