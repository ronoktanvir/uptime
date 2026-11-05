# ADR-0022: Sender authority

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **SUPERSEDED — reviewer HMAC; residual risks remain**.

## Decision and alternatives

Retain exact-request challenge binding, but reject the password-derived human HMAC proposal in favor of ADR-0026 public-key reviewers; source credentials evolve separately in ADR-0029.

Password-derived HMAC is easy to provision but leaves a server-side signing equivalent and offline password attacks. Passkeys provide hardware/platform origin binding with enrollment costs. Local asymmetric files avoid a server signing secret but retain file and browser exposure.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/22-sender-authority.json](reviews/22-sender-authority.json); its sanitized input is [packets/22-sender-authority.md](packets/22-sender-authority.md). Receipt time: `2026-11-05T00:20:47.946567+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `583bd9d0-ccad-4575-bbdc-706f5ea5394d`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus strongly prefers WebAuthn over custom password crypto, explains the password-equivalent HMAC verifier, and rejects nonextractable-key claims against XSS. It asks for canonicalization, downgrade, race and cross-tenant tests.

**Root position and reconciliation:** Accept the verifier-compromise dissent and supersede the human HMAC approach. Do not preserve the packet’s suggestion that in-memory nonextractability solves XSS. Exact host/origin and request binding remain worthwhile within the narrower browser-origin threat model. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

auth_keys now uses P-256 and public verification; auth.challenge reports ES256. HMAC survives only in a restricted synthetic service compatibility path, not as human reviewer authentication.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/auth_keys.py](../../../uptime/auth_keys.py)
- [uptime/auth.py](../../../uptime/auth.py)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_v4_authority.py tests/test_source_config_v4.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A human enrollment requiring a shared password-derived server signing key would falsify supersession. Any claim that injected same-origin script cannot sign is unsupported without a different authenticator/threat boundary.

## Versioned rollback

Disable reviewer mutations and revoke enrollment; migrate by new asymmetric enrollment. Do not roll back to password-HMAC or reactivate old credentials. Preserve prior protocol receipts as historical. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `d8e87da3f7a7061f6789825d8ac983e37c54cea1cf34a0b6d20c08417bd5b2f4` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `edcd883aaf7d49ddb8e0ea625554b459db307eb3eb9823b87dfae82b1bfd3b53`.
- Review-prompt SHA-256 recorded by receipt: `5548fda4551e898bbe4664692a9890fc07a6f3c8fc36fce9c2c5ecef08002868` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
