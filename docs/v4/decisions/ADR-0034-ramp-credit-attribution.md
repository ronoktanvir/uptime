# ADR-0034: Ramp credit attribution

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL — bounded attribution only**.

## Decision and alternatives

Keep native credit observations separate from claims/awards, require exact scoped bindings, and label reciprocal Ramp credit/bill views as same-system consistency checks.

Amount/name matching misattributes credits. A fabricated negative bill or credit API invents financial state. ERP/GL/vendor corroboration adds independent evidence and cost. General N:M attribution requires explicit allocations absent from this base sync.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/34-ramp-credit-attribution.json](reviews/34-ramp-credit-attribution.json); its sanitized input is [packets/34-ramp-credit-attribution.md](packets/34-ramp-credit-attribution.md). Receipt time: `2026-11-05T00:20:12.164307+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `71676943-388e-4aff-949a-ae5f24d244f6`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus objects that two Ramp views are not independent corroboration and recommends N:M allocations. It distinguishes normal remaining-balance decreases from reversals and challenges archive semantics.

**Root position and reconciliation:** Accept source-independence and allocation dissent. Narrowly disagree that a second financial system is necessary merely to say “Ramp observed applied”; that label reports Ramp’s own state, not independent vendor confirmation, attributable recovery or cash. A separate award/binding is required for attribution. The implementation conservatively quarantines archives/conflicts rather than claiming automatic resolution. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

ramp_credit_sync binds one award payload per tenant/credit ID and journals cumulative deltas; it is not generalized N:M. Its backing ledger permits only SIMULATED_VENDOR awards. It preserves actual_recovery=null and isolates draft applications. The live reported credit list is empty.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/ramp_credit_sync.py](../../../uptime/ramp_credit_sync.py)
- [uptime/allocations.py](../../../uptime/allocations.py)
- [docs/v4/RAMP-CREDIT-SYNC.md](../../../docs/v4/RAMP-CREDIT-SYNC.md)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_ramp_credit_sync_v4.py tests/test_allocation_ledger.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A repeated cumulative read adding value, unmatched reciprocal links advancing allocation, reversed application remaining current, or a split/multi-award credit silently mapped as one award falsifies the sync. General N:M and actual awards require ADR-0040.

## Versioned rollback

Stop links/promotions and preserve quarantined history; do not delete bindings or rewrite consumed capacity. Any reversal/unquarantine needs a reviewed append-only resolution. Reverting the importer does not undo provider applications. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `b23869b46492b951bab1fd7e6338e7ec5131d1f9c8505e4a048beb59b49d4b35` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `473763250909c294eba4a911f16a0ab53b4d7326958f2ea1ec558b69bd09a54c`.
- Review-prompt SHA-256 recorded by receipt: `022be30d8e9e5d0ffb06f8efc8577aa9071359b3ec6f09330bcc268ff17c0522` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
