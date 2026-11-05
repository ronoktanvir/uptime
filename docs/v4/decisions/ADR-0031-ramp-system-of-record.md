# ADR-0031: Ramp system of record

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL — reads observed; write enforcement unproven**.

## Decision and alternatives

Treat Ramp as the system of record for financial observations and Uptime as the owner of versioned contract/evidence interpretation and provisional findings.

Flat CSV/mock AP state cannot establish native authority. Live pass-through is fresh but loses replay evidence. Versioned bounded snapshots preserve provenance at the cost of staleness; webhooks plus snapshots remain dependent on separate registration.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/31-ramp-system-of-record.json](reviews/31-ramp-system-of-record.json); its sanitized input is [packets/31-ramp-system-of-record.md](packets/31-ramp-system-of-record.md). Receipt time: `2026-11-05T00:20:00.925214+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `1533dac1-e406-4936-965d-fd5ef2bbdc40`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus warns snapshots can become a shadow ledger, calls for exact IDs/hash/fetched time and refresh before action, and rejects inferring enforced write denial from absent scope metadata.

**Root position and reconciliation:** Accept staleness and scope dissent. “Real” here means an actually fetched sandbox record, not a customer loss or production invoice. Do not perform a write merely to satisfy an Opus falsifier. Two schema hashes in feasibility show documentation drift; pin the observation, not an everlasting API assertion. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

ramp_records bounds read operations, validates native IDs and captures resource completeness. ramp_workspace preserves tenant/business capture history. The token receipt is metadata-only with writes_attempted=false. Existing local docs describe POST agreements as a read query; no new external verification was performed.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/ramp_records.py](../../../uptime/ramp_records.py)
- [uptime/ramp_workspace.py](../../../uptime/ramp_workspace.py)
- [docs/v4/RAMP-FEASIBILITY.md](../../../docs/v4/RAMP-FEASIBILITY.md)
- [docs/v4/evidence/ramp-bill-grants.json](../../../docs/v4/evidence/ramp-bill-grants.json)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_ramp_records_v4.py tests/test_ramp_workspace_installation.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** An ambiguous name/amount join auto-resolving, stale captures treated as current authority, or partial pagination labelled complete falsifies the boundary. A native write claim requires separate authorized execution/readback, absent here.

## Versioned rollback

Disable import-dependent findings, retain immutable capture history and source hashes, and return stale/unavailable status. Restore a compatible reader without replacing current Ramp state with an old snapshot. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `fcd55c4f2a3bfa429c52453395e80a14e0512c92ba8357b6f42f943f3589af1f` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `a5d0c8061407775e7710026707184c77852c439a6318db383e15edad27e630c6`.
- Review-prompt SHA-256 recorded by receipt: `2e3594c75fe759cf65bcf2a1dbea655983b81687e8b8e357d2bebecac597efaa` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
