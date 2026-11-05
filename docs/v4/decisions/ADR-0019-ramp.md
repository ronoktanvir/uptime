# ADR-0019: Ramp

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **BLOCKED — native writes**.

## Decision and alternatives

Keep Ramp access pinned to the exact sandbox HTTPS host, explicit requested grants and object identity. Do not broaden scopes or bypass absent grants through a human CLI.

Broader grant requests or UI substitution obscure authority. A dedicated administrator-configured sandbox app could supply exact grants but needs separate administrative action. Recorded/mocked transport supports reversible development without proving provider writes.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/19-ramp.json](reviews/19-ramp.json); its sanitized input is [packets/19-ramp.md](packets/19-ramp.md). Receipt time: `2026-11-05T00:20:32.232373+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `e993b907-e1b6-44af-9147-1cf3db9748ee`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus challenges the assumption that a draft probe is harmless or already authorized, and asks for exact scope explanation, sandbox confirmation, chosen vendor, cleanup policy and same-ID readback.

**Root position and reconciliation:** The token-only receipt establishes omitted reported bills:write, not HTTP enforcement, an administrator setting or its cause. Accept Opus’s distinction but do not perform its suggested write falsification without separate authority. This task made no calls. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

ramp-bill-grants.json explicitly says writes_attempted=false and admin_configuration=NOT_INSPECTED. Ramp SDK exposes guarded methods; code paths and mocks do not establish positive provider capability.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/ramp.py](../../../uptime/ramp.py)
- [docs/v4/evidence/ramp-bill-grants.json](../../../docs/v4/evidence/ramp-bill-grants.json)
- [docs/v4/RAMP-FEASIBILITY.md](../../../docs/v4/RAMP-FEASIBILITY.md)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_ramp.py tests/test_ramp_records_v4.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A redirect followed, unexpected grant accepted, ambiguous vendor selected or stale proof reused falsifies local controls. Native write status changes only with authorized exact-object execution and readback; a denied HTTP write would establish that denial only.

## Versioned rollback

Disable the write adapter and revoke local capability; preserve scope and outbox receipts. Any cleanup of a provider artifact is a separate authorized action, not an automatic rollback. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `19b78882cef5da15f15092d94621f342e11f57a96c97327ddd5991074af4e64a` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `e0c383762fe40c1cc4db95da4b48bd6a19af2c319417f8266f97a14c1970f574`.
- Review-prompt SHA-256 recorded by receipt: `4fadf8f9aef708f585640d3d3dc67f7818660c3708b65f368aedf0b45ad69eea` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
