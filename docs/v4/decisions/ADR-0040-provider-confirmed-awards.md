# ADR-0040: Provider confirmed awards

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PROPOSED — staged companion; not integrated proof**.

## Decision and alternatives

Keep native credit observations unattributed unless a separately authenticated vendor award and exact independently attested allocation bind them; realized cash stays null in sandbox.

Always unattributed is conservative but hides legitimate attribution. Amount-matching fabricates links on collisions/splits. Typed explicit N:M allocations can support justified attribution but require independent authority, capacity constraints and reconciliation operations.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/40-provider-confirmed-awards.json](reviews/40-provider-confirmed-awards.json); its sanitized input is [packets/40-provider-confirmed-awards.md](packets/40-provider-confirmed-awards.md). Receipt time: `2026-11-05T00:27:36.529561+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `c1d3a523-4dc9-4c84-bf32-543787f71ad8`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus prefers attested bindings but says independence needs evidence and Ramp-applied is not realized cash. It requires exact split allocation, one-minor-unit rejection, reversal handling, type-safe provenance and per-binding human sign-off.

**Root position and reconciliation:** Accept independence and cash dissent. Two Ramp representations are one system. Local signatures attest statements under enrolled keys; they do not by themselves verify vendor legal authority or a bank refund. The stable ledger’s simulated-only restriction remains. A staged companion must not be reported as integrated/customer-ready. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

At inspection, native_awards has staged ramp_award_attribution.py plus tests/CLI/docs, not a committed integrated implementation. It defines ACTUAL_NATIVE/MOCK stores, Ed25519 roles and SQL allocation caps; summary keeps actual_recovery and actual_recovered_cash null. The stable release has no such companion and reports zero captured credits.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/allocations.py](../../../uptime/allocations.py)
- [uptime/ramp_credit_sync.py](../../../uptime/ramp_credit_sync.py)

Staged worker code: `/Users/ronoktanvir/.local/share/uptime-engineering/worktrees/native_awards/uptime/ramp_award_attribution.py`; inspected SHA-256 `e41b1970750585fc6a372223fc3748a6d13b655526f99c7c7b31a0e0856e232c`. Interface report: `/Users/ronoktanvir/.local/share/uptime-engineering/tasks/INTERFACES-awards.md`. Its test claim is not independently rerun here. Proposed focused command in that owner checkout: `UV_OFFLINE=1 uv run --locked pytest tests/test_ramp_award_attribution.py -q`.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_ramp_credit_sync_v4.py tests/test_allocation_ledger.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A fixture flag entering real provenance, shared upstream presented as independent award confirmation, N:M without exact allocations, cross-account fan-out, over-allocation or a reversal leaving current attribution falsifies the proposal. Closure requires committed integration, independent authority verification and genuine positive evidence, absent here.

## Versioned rollback

Disable the companion and retain signed claims/awards/observations and allocation history. Suspend attribution on conflict; do not clear consumed capacity or edit a vendor award. Any resolution/reversal requires a reviewed append-only design. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `b80147597c98e19cbc0b03357fbef0bd43649a371637376ac2f0703d67d5a68e` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `50848caf63868bda78fc51244f467930078b3d12b73a99eaea0b400b5da0d640`.
- Review-prompt SHA-256 recorded by receipt: `bf547c37cf8f1b80bc6e1011afa55d328e09fa0588893e284ad12a3ce50645e6` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
