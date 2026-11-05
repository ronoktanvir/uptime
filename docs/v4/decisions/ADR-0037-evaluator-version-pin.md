# ADR-0037: Evaluator version pin

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL — stronger pin implemented**.

## Decision and alternatives

Pin candidate approval to the actual bounded evaluator/compiler/profile source manifest and reject incompatible active or rollback artifacts.

Ignoring semantic changes silently extends approval. Hashing the entire repository suspends unrelated work. Self-declared semantic versions are selective but can miss a required bump; bounded source hashes conservatively invalidate even comment-only changes in relevant modules.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/37-evaluator-version-pin.json](reviews/37-evaluator-version-pin.json); its sanitized input is [packets/37-evaluator-version-pin.md](packets/37-evaluator-version-pin.md). Receipt time: `2026-11-05T00:20:24.690297+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `d01e66e8-5a52-4664-b9d5-2079e78f1f13`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus identifies unenforced version bumps as the central flaw and asks for golden-output enforcement, compatibility ownership, stale-link rejection and exact unposted fractions.

**Root position and reconciliation:** Accept the self-declared-version objection. The inspected code goes beyond the packet: semantics revisions hash a bounded list of actual source files. This avoids relying only on a manual bump, at the cost of unnecessary reapproval for some harmless edits. Runtime/dependency changes outside that list still need release review. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

vendor_terms SEMANTICS_REVISIONS hashes shared and profile-specific source files; candidate_version includes that digest. Registry compatibility clears unavailable active capability and blocks incompatible dispatch/rollback while retaining recorded history.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/vendor_terms.py](../../../uptime/vendor_terms.py)
- [uptime/vendor_registry.py](../../../uptime/vendor_registry.py)
- [uptime/vendor_resource_eval.py](../../../uptime/vendor_resource_eval.py)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_vendor_catalog.py tests/test_vendor_resource.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Changing a hashed evaluator without changing candidate compatibility, dispatching an incompatible restored artifact, or rounded-zero credit remaining claimable falsifies the pin. No comprehensive dependency-closure or cross-runtime semantic equivalence is claimed.

## Versioned rollback

Revoke incompatible active capability; restore a mutually compatible code/artifact pair or create a newly tested/reviewed revision. Never retrofit a new semantics digest onto old approval. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `731321bc207a26c650c14915c9d4975d4cb394daea7e968249770de2b387795e` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `a0fc0fa40a83bf3caf983e9a4e86ffd3c2dc662a2661c2df92a74720d8c6b24f`.
- Review-prompt SHA-256 recorded by receipt: `287b6b8b84ead116ec8f193c100b7f98923f09b7d0fa36f66c464219b12fecd2` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
