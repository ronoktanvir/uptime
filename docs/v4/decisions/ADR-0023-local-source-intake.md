# ADR-0023: Local source intake

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL — refined by ADR-0029**.

## Decision and alternatives

Provision source-specific authority offline and deliver exact signed event bytes; the browser may neither mint source grants nor choose sender authority.

Browser bearer secrets expose source identity; service-wide administration is overbroad. Per-source HMAC reduces operational setup but lets the verifier forge messages. Ed25519 or mTLS costs key ceremony and narrows verifier trust.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/23-local-source-intake.json](reviews/23-local-source-intake.json); its sanitized input is [packets/23-local-source-intake.md](packets/23-local-source-intake.md). Receipt time: `2026-11-05T00:20:48.584821+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `2cf1c844-3378-4bfc-a659-fe633d5c09cf`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus favors asymmetric keys, source-isolated credentials, owner-only files and server-derived scope. It asks for immediate revocation, unknown-key rejection and egress evidence, not a claim that CLI possession proves provider identity.

**Root position and reconciliation:** Accept the asymmetric refinement and per-request revocation requirement. The operator owns local source enrollment; this is a synthetic/local delivery interface, not an external vendor inbox or real customer connector. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

SOURCE-INTAKE and source_config implement protected source files, exact role/scope grants and launcher configuration. Authority resolves the grant independently of event payload and rejects incompatible scope. Full real-loopback delivery still depends on listener permissions.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/source_config.py](../../../uptime/source_config.py)
- [scripts/provision_sources.py](../../../scripts/provision_sources.py)
- [scripts/deliver_evidence.py](../../../scripts/deliver_evidence.py)
- [docs/v4/SOURCE-INTAKE.md](../../../docs/v4/SOURCE-INTAKE.md)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_source_config_v4.py tests/test_correspondence_api.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Source A presenting source B’s scope, revoked credentials accepted on the next request, duplicate domain events adding evidence twice, or secret values printed by the CLI falsifies the boundary.

## Versioned rollback

Revoke/rotate the individual source in protected configuration, stop intake if configuration is invalid, and preserve previously accepted event provenance. Restore only compatible public config; never restore a compromised private credential. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `ce6c37d0cf71f0584d0901dec2efad97e4173eab893e88ac30704342642f40f3` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `e82ab96587eeb06f8c649a582528b6d56a57f7e0b654f9199aabc97336fa925b`.
- Review-prompt SHA-256 recorded by receipt: `f0ed4b6074f19551c5e98436168c980fe160114d53429ddf56f8b7a9e0d9287c` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
