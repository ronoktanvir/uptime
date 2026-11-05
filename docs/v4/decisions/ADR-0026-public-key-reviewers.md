# ADR-0026: Public key reviewers

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Use random P-256 reviewer keys provisioned offline; store public verification material server-side and bind single-use challenges to the exact runtime/request.

Password-HMAC exposes signing authority on verifier compromise. WebAuthn offers stronger authenticator isolation and has viable virtual CI authenticators. Local key files support this offline sandbox but are exportable, readable by the OS user and exposed to page script before import.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/26-public-key-reviewers.json](reviews/26-public-key-reviewers.json); its sanitized input is [packets/26-public-key-reviewers.md](packets/26-public-key-reviewers.md). Receipt time: `2026-11-05T00:21:02.816861+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `e06c5bbb-284f-446c-9163-983d348de013`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus supports improvement over HMAC but rejects the packet’s weak WebAuthn CI rationale, nonextractability as XSS protection, and blanket low-S rejection because ordinary WebCrypto signatures need not be low-S.

**Root position and reconciliation:** Accept those objections. Choose local files only for the stated sandbox usability boundary, not because WebAuthn cannot be tested or because ports alone justify custom identity. Replay protection keys on consumed challenge, not signature encoding; private-key theft, XSS, extensions and OS compromise remain material residual risks. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

auth_keys verifies P-256 signatures; Authority.consume atomically removes the challenge. File creation is exclusive outside the repository. No observed cryptographic signature establishes a person’s intent, organizational authority or actual human activation.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/auth_keys.py](../../../uptime/auth_keys.py)
- [uptime/auth.py](../../../uptime/auth.py)
- [web/app.js](../../../web/app.js)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_v4_authority.py tests/test_v4_authority_browser.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Replayed alternate ECDSA representation reusing a challenge, changed mode/origin/body acceptance, fixture key accepted as human, or revoked key retaining mutation authority falsifies controls. XSS resistance is not claimed.

## Versioned rollback

Disable approvals, revoke public enrollment and rotate to a newly provisioned key. Retain old public-key provenance and receipts; never restore leaked private material from a backup. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `6b0a4a175d41b4eb7a632641f66f35f04e917682ec87941adfbe132858be1efb` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `c726ed9aa2f70d6fda2e25537666a375db54c79f2317d84623ee89534af41759`.
- Review-prompt SHA-256 recorded by receipt: `1cb86bac95e18eb1a870e5344116115b75666698df91705cb46fa7ac142ec9bb` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
