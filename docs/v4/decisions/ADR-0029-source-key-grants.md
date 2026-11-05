# ADR-0029: Source key grants

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Use source-specific Ed25519 grants with server-side scope and public verifiers, fresh runtime-bound exact-body signatures, and per-request protected-config revocation.

HMAC is simpler but lets the app forge events. mTLS shifts custody to transport infrastructure. Ed25519 narrows verifier exposure but requires issuance, rotation and source-binding administration; synthetic HMAC compatibility must remain isolated.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/29-source-key-grants.json](reviews/29-source-key-grants.json); its sanitized input is [packets/29-source-key-grants.md](packets/29-source-key-grants.md). Receipt time: `2026-11-05T00:21:16.758286+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `88abacff-193d-406d-b541-60211a087c5f`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus favors Ed25519 but objects to restart-only revocation, unspecified durable replay protection, downgrade paths and caller-controlled Origin. It requests nonce races, stale config and key-ID substitution tests.

**Root position and reconciliation:** Accept immediate revocation and the fact that a non-browser Origin is not identity. The implementation reloads protected grants each delivery; fresh runtime instance invalidates old transport proofs after restart while durable event identity handles domain duplicates. Do not call these local keys authenticated real vendor identities. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

Authority.service uses SourceRegistry.lookup per request, exact raw body/path, tenant/mode/instance and nonce timestamp. Source files enforce ownership/link constraints; HMAC/asymmetric mixtures are rejected and launcher enrollment is asymmetric.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/source_config.py](../../../uptime/source_config.py)
- [uptime/auth.py](../../../uptime/auth.py)
- [docs/v4/SOURCE-INTAKE.md](../../../docs/v4/SOURCE-INTAKE.md)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_source_config_v4.py tests/test_workspace_tenant_v4.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A revoked key accepted on the next delivery, an old-process proof accepted after restart, HMAC downgrade into a configured asymmetric grant, or cross-source scope substitution falsifies the boundary.

## Versioned rollback

Revoke source/public grant and rotate private key offline; invalid config closes intake. Preserve accepted receipts and key/grant digests. Restoring config must not resurrect revoked authority. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `2d2f637a6cb450362379459930516fbd36968743da0fa33bb9dc58f28d764295` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `c7b2f776871a8d0f1bc95add400e3a8a4032e4b09382025b961186a409135e39`.
- Review-prompt SHA-256 recorded by receipt: `57c6d1b2e27c27a0bbd8fdd006866a6211423c3abf6b00d59fb853d4c2537fdd` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
