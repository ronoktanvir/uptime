# ADR-0027: Active remedy join

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Join correspondence to exactly one scoped active adapter and source-bound fee/evidence set, rechecking its version and revision at the write boundary.

Caller-supplied evaluation digests are quick but authorize unsourced entitlement. A Twilio-only fallback hides unsupported coverage. Manual review for every claim avoids premature automation but still needs effective terms and scope evidence.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/27-active-remedy-join.json](reviews/27-active-remedy-join.json); its sanitized input is [packets/27-active-remedy-join.md](packets/27-active-remedy-join.md). Receipt time: `2026-11-05T00:21:03.666060+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `d6d3356e-68a5-456e-a5ad-68605ff56d1c`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus objects that today’s ACTIVE installation may not govern a past incident, requests effective-dated joins, and suggests overlays only narrow public rules. It also challenges transaction claims for external sends.

**Root position and reconciliation:** Accept effective-time and external-send cautions. Dissent from a universal narrow-only overlay rule: a separately evidenced negotiated agreement can lawfully change a public filing term; widening cannot be inferred from a flag or public text. Until such authority is established, refuse. Current activation is necessary, not sufficient proof of historical applicability. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

vendor_registry.evaluate_active_db rechecks active version/revision; correspondence_resource assembles scoped provider, customer and billing facts. Overlay dates and governing evidence are explicit. This inspection does not establish every historical plan-change case or external outbox delivery.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/vendor_registry.py](../../../uptime/vendor_registry.py)
- [uptime/correspondence_resource.py](../../../uptime/correspondence_resource.py)
- [uptime/vendor_eval.py](../../../uptime/vendor_eval.py)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_correspondence_resource.py tests/test_vendor_resource.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A plan upgrade after an incident creating retroactive entitlement, multiple matching fee lines being chosen silently, or rollback racing approval without invalidation falsifies the join.

## Versioned rollback

Revoke the installation, retain historical cases, and append reevaluation under a reviewed applicable version. Incompatible versions must stay blocked; do not rewrite the case to look originally evaluated under new terms. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `d1c11041dec8198d8986994b62800ddda5e571ec346b4d84a2a3a7e0e99be64c` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `4400f9aba5dd9ec34f07656cbc1c0d91d072cdb0b2efe9505c7a75fc49323ff5`.
- Review-prompt SHA-256 recorded by receipt: `2f2b1e27b186fa4b49d64bee77321e31ce29020ab13e6c94e04bc2723376cb13` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
