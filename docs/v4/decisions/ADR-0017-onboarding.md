# ADR-0017: Onboarding

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Keep vendor onboarding declarative, source-cited and bounded to supported availability families, with separate overlay, independent tests, versioned promotion and revocation.

Vendor-specific executable plugins are predictable but do not demonstrate unseen ingestion. Arbitrary generated code expands the attack surface. Human-authored declarative rules, raised by Opus, minimize semantic trust at the cost of manual work.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/17-onboarding.json](reviews/17-onboarding.json); its sanitized input is [packets/17-onboarding.md](packets/17-onboarding.md). Receipt time: `2026-11-05T00:20:26.021085+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `c2745989-9cd5-4f29-8c94-c3093db70e1d`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus rejects the unmeasured ordinary-prose coverage claim and asks for fresh unseen evidence, source exclusion guarantees, monotonic revisions, stale-link rejection and named human approval.

**Root position and reconciliation:** The packet aims at autonomous unseen ingestion. Accept that a bounded parser plus curated tests is insufficient proof of generalization. Authentication of a sandbox operator does not demonstrate human interpretation or human activation; preserve that distinction even when the registry says ACTIVE. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

VendorRegistry persists immutable artifacts/events and increments revision; act binds approval and activation to the same authenticated subject. reviewer_kind is inferred from a scripted- prefix versus authenticated_reviewer, which does not independently establish a human act.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/vendor_registry.py](../../../uptime/vendor_registry.py)
- [uptime/vendor_terms.py](../../../uptime/vendor_terms.py)
- [uptime/vendor_api.py](../../../uptime/vendor_api.py)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_vendor_catalog.py tests/test_vendor_rejections.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A→B→A reusing old approval, malformed sources restoring ACTIVE, stale action links succeeding, or activation failing to affect dispatch falsifies implementation. Unseen-vendor success remains unestablished in this ADR; no heldout data was accessed.

## Versioned rollback

Revoke the active installation or append rollback to a compatible previous artifact, leaving all revisions and dispatch receipts intact. A restored source must receive a new monotonic revision and required review. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `4c54ba5e0d9e22c0572e7cf98a624194b5f5f278cf61689a7220b43282a55164` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `525f151a1a3b21dff1a1649a0eba7bdf3590e9e7c79754516a70b95968e8aa5a`.
- Review-prompt SHA-256 recorded by receipt: `d62e7a807e750da83aee783caca6ab45d10bb7e067b67a4a7a55d3e64e32e676` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
