# ADR-0016: Allocation

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Use one-host persistent SQLite allocation accounting with canonical scope, integer USD cents and transaction-level cumulative bill/credit ceilings.

In-memory totals lose restart history; case-local totals miss shared capacity. A full double-entry service or serializable remote database supports broader deployment but adds operational and migration work. SQLite is bounded to the installation’s single database.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/16-allocation.json](reviews/16-allocation.json); its sanitized input is [packets/16-allocation.md](packets/16-allocation.md). Receipt time: `2026-11-05T00:20:16.123929+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `b5f81e17-29da-4b8c-80b1-cb52172f78d9`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus endorses single-host scope and requires BEGIN IMMEDIATE, append-only corrections, exact currency scope, crash tests and quarantine of incompatible migration rows. Multi-host/network-filesystem guarantees are not established.

**Root position and reconciliation:** Accept the global ledger and single-host constraint. The packet proposed normalized minor units generally; actual settlement is narrower: USD only and SIMULATED_VENDOR awards. A ledger entry is neither a real award nor money movement. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

AllocationLedger starts BEGIN IMMEDIATE and SQL triggers enforce capacity and immutable rows. The award source CHECK admits only SIMULATED_VENDOR. Legacy migration has separate preserved rows; no general live accounting or reversal workflow is established.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/allocations.py](../../../uptime/allocations.py)
- [uptime/reconciliation.py](../../../uptime/reconciliation.py)

Audit: [durable audit results](../audit/RESULTS.md), especially its source pin, unavailable browser observations and failed release flags. This report does not certify the later inspected main revision.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_allocation_ledger.py tests/test_v4_audit_ledger.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Two concurrent USD80 allocations exceeding a USD100 bill, a one-cent allocation becoming zero, a currency crossover, or restart duplicating consumption falsifies the ledger. Real award ingestion remains blocked by source type and requires ADR-0040 integration.

## Versioned rollback

Stop new allocations; retain the journal and legacy rows. Restore compatible reads from a versioned backup or code revision only after schema checks. Resolve bad entries through a separately reviewed append-only correction; deleting rows is not rollback. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `6c4bbc9c99752d0b53a95d3933399d6a6f885649aab2a08868506ccacd1f9cbc` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `4524d39d5c162577098fddd17717905eb8e2175c9b53dd15a5fd5681aa5be96b`.
- Review-prompt SHA-256 recorded by receipt: `88ef76182ef21c174413698c512b1ef320ff617fcd6154f01a3285f79ce997ba` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
