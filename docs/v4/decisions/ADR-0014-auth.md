# ADR-0014: Auth

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Use offline-enrolled named reviewers and nonambient, exact-request proofs; consequential actions remain interlocked. The final public-key design is recorded in ADR-0026.

Port/SameSite cookies reduce interaction cost but cannot isolate sibling ports. An enterprise IdP provides recovery and organizational identity at the cost of external setup. Local challenge proofs support an isolated installation but add enrollment, restart and multi-tab friction.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/14-auth.json](reviews/14-auth.json); its sanitized input is [packets/14-auth.md](packets/14-auth.md). Receipt time: `2026-11-05T00:20:16.123679+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `248d95ee-0ebe-47ca-b257-2459d4c5b2ec`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus supports the direction but distinguishes a hostile browser origin from a hostile local process. It calls out XSS, DNS rebinding, concurrent replay, recovery and clock handling; it explicitly did not inspect the cited code.

**Root position and reconciliation:** The packet rejects ambient reviewer cookies. Accept Opus’s narrower threat model: exact origin checks protect this protocol against sibling browser requests, not same-origin XSS, copied private keys or OS compromise. Do not describe local enrollment as enterprise identity. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

Authority.require_origin checks literal Origin and Host; reviewer requires an exact POST without query, hashes raw bytes, and consumes a challenge under a lock. The independent audit still reports the real sibling-browser observation UNAVAILABLE; HTTP tests cannot close it.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/auth.py](../../../uptime/auth.py)
- [uptime/auth_keys.py](../../../uptime/auth_keys.py)
- [scripts/serve.py](../../../scripts/serve.py)

Audit: [durable audit results](../audit/RESULTS.md), especially its source pin, unavailable browser observations and failed release flags. This report does not certify the later inspected main revision.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_v4_authority.py tests/test_v4_authority_browser.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A sibling-origin browser obtaining usable mutation authority, concurrent reuse accepting twice, or a changed body passing falsifies the boundary. Closing PARTIAL requires the actual browser observation on the frozen release; XSS and same-user OS resistance are explicitly not established.

## Versioned rollback

Disable local approvals, invalidate sessions by restart and revoke compromised enrollment. Preserve audit rows and restore only a reviewed code revision; never restore the old ambient-cookie authority. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `fcc88001f027fb1fdbcc129ca3eea2fd5eb61692c49759693b13cb69f80a404b` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `02370e550b115c8b1a8bae128ed620453a30db57500233ffdc537e5400483474`.
- Review-prompt SHA-256 recorded by receipt: `05fff3a4964b611d807b9adc94ae35925c17ed9254764c5b4f89e3fc17d5bedc` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
