# ADR-0030: Tenant reviewer mandates

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Bind one tenant to each installation and require separately issued exact-action mandates for sandbox/non-default reviewer mutations and native effects.

A global reviewer or caller-selected tenant is easy but allows substitution. Per-request broad scopes leave stale estimate risk. Exact signed mandates add ceremony and expiry/retry work while binding authority to stored evidence and amounts.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/30-tenant-reviewer-mandates.json](reviews/30-tenant-reviewer-mandates.json); its sanitized input is [packets/30-tenant-reviewer-mandates.md](packets/30-tenant-reviewer-mandates.md). Receipt time: `2026-11-05T00:21:17.341599+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `dc8ae071-f1c3-43c6-97ec-d72cd6cd826a`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus requires server-derived signer scope, independent escalation authority and isolation of the broad simulated operator path. It challenges independence of enrollment and recommends out-of-band dual control.

**Root position and reconciliation:** Accept that login alone is not a mandate. The legacy broad operator is limited to default replay fixture mode; sandbox and other tenants require mandates. Independent signing keys prove distinct custody only to the extent enrollment verifies it, not legal or commercial authority. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

Authority.reviewer requires mandates outside fixture replay; authorize_native requires sandbox, non-rehearsal AuthorizedReviewer and consumes exact-effect authority. mandates binds workspace, issuer/reviewer, body and financial decision; documentation separates issuer registration from reviewer enrollment.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/mandates.py](../../../uptime/mandates.py)
- [uptime/auth.py](../../../uptime/auth.py)
- [docs/v4/REVIEWER-MANDATES.md](../../../docs/v4/REVIEWER-MANDATES.md)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_signed_mandates.py tests/test_workspace_tenant_v4.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A cap+1 amount, changed estimate, wrong tenant/audience, finance key granting itself rights, or default replay bypass on a sandbox tenant falsifies the mandate boundary.

## Versioned rollback

Revoke mandate or issuer, disable native dispatch and preserve consumed tickets and decision evidence. New enrollment/mandate is required after rotation; never restore consumed authority by database rollback. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `accc971af06debea1dfc62b147e140f249fdbbbd65db70442d3e0d35d7026255` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `7748b96b01de797517f0e3515496242eb98cc0e1ae00dfa265d6f51baf61fd6b`.
- Review-prompt SHA-256 recorded by receipt: `1f04042ba76b99fed659295753f322eab143dcc07d8fc930245702fb2945efc2` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
