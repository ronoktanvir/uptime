# ADR-0033: Ramp inbound security

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL — hex correction; registration blocked**.

## Decision and alternatives

Validate an optional isolated receiver using hex HMAC-SHA256 over the exact raw body, persist/deduplicate before acknowledgment, and keep registration/network exposure separately blocked.

Polling reduces inbound exposure but cannot invent an approval-trigger identity. A managed relay adds another data custodian. An isolated listener supports protocol testing but has no provider-origin evidence until registered and independently witnessed.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/33-ramp-inbound-security.json](reviews/33-ramp-inbound-security.json); its sanitized input is [packets/33-ramp-inbound-security.md](packets/33-ramp-inbound-security.md). Receipt time: `2026-11-05T00:20:00.925816+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `24f0e5ae-9b3e-48e6-9073-5ec68d7ab021`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus explicitly refuses to trust the packet’s base64/signature/challenge assertions and says local fixtures cannot validate a forbidden registration end to end.

**Root position and reconciliation:** Accept and preserve the correction: packet 33 says base64; the supplied guide, implementation and worker status specify a hexadecimal digest over raw bytes. Do not silently edit the historical packet. Generated local signing keys test verification logic, not Ramp origin. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

ramp_webhooks._parse requires 64 hex digits and compares hmac.new(secret, raw_body, sha256).hexdigest(); it rejects duplicate JSON keys, wrong business/service key and unknown events. RAMP-FEASIBILITY documents the corrected encoding. No live registration or tunnel is claimed.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/ramp_webhooks.py](../../../uptime/ramp_webhooks.py)
- [docs/v4/RAMP-FEASIBILITY.md](../../../docs/v4/RAMP-FEASIBILITY.md)

Correction provenance: `/Users/ronoktanvir/.local/share/uptime-engineering/tasks/STATUS-ramp-workflow.md`, worker commit `c61c38480b7c9ef6196f0099c26d976e3f8ac9e1`; Local supplied guide `/Users/ronoktanvir/.local/share/uptime-engineering/reference/webhooks.txt` was also checked at lines 240–247 (exact raw body and hex sample); SHA-256 `fb6ef27424ce859943784d883eefef8b84ab4aa0810b3a919ce07fb04e2014bb`. No external fetch was made by the ADR owner.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_ramp_workflow_webhooks.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A one-byte rewrite or JSON reserialization retaining a valid signature, foreign business accepted, reset not invalidating pending state, or acknowledgment before durable persistence falsifies local protocol. Provider authenticity remains blocked pending authorized registration evidence.

## Versioned rollback

Disable the receiver, revoke/rotate subscription credentials through separately authorized operations if ever registered, and retain dedup/reset/quarantine history. Do not clear event IDs to enable replay. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `3e41bf3e0f0c092db6ae30cd774b4a76d6df658e014b617a6dfd724d6b8184d7` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `fbac24849e961803f7e5ae9efb7b1d36b9c57c9ffe71d3e4c33d0ad6ce28bd54`.
- Review-prompt SHA-256 recorded by receipt: `9be6ed92a9ae685284910a5ccc58be16ecf638479ed2ee3c60f5030dc2344c2f` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
