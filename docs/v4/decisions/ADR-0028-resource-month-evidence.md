# ADR-0028: Resource month evidence

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Extend only the bounded resource-month evidence profile with scoped interval unions, exact fee attribution and contractual filing boundaries; retain earlier parser refusal as a failure.

Hardcoding the revealed vendor or authoring its adapter manually can pass a replay but does not show autonomous generality. Executable generation with credentials violates the trust boundary. Finite declarative expansion costs interpretation and evidence maintenance.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/28-resource-month-evidence.json](reviews/28-resource-month-evidence.json); its sanitized input is [packets/28-resource-month-evidence.md](packets/28-resource-month-evidence.md). Receipt time: `2026-11-05T00:21:12.198720+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `8484c67b-383a-4a05-947b-6fc8e78612cb`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus says a retest after seeing failed input is no longer blind. It requires a fresh independently chosen sealed corpus, definition/span coverage, explicit half-open time boundaries and separate evidence for post-claim verification.

**Root position and reconciliation:** Accept the loss-of-blindness objection. Existing test counts do not rehabilitate a failed unseen input. Record extension as bounded engineering; this ADR neither accesses heldout data nor claims the unseen-vendor gate passed. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

vendor_resource_eval exposes scope checks, interval measurement, fee and deadline functions. It represents billing cycles explicitly instead of replacing them with fixed days. Implementation is observable; generalization remains a separately witnessed release obligation.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/vendor_resource_eval.py](../../../uptime/vendor_resource_eval.py)
- [uptime/vendor_resource_terms.py](../../../uptime/vendor_resource_terms.py)
- [uptime/correspondence_resource.py](../../../uptime/correspondence_resource.py)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_vendor_resource.py tests/test_correspondence_resource.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A ±1-second boundary error, unresolved definition accepted, missing cycle schedule invented, or verification derived from eligibility itself falsifies the profile. Fresh freeze-before-reveal independent evidence is required to close the generalization claim.

## Versioned rollback

Revoke affected profile dispatch, retain failure and source/operator versions, restore only compatible artifacts and append reevaluation differences. Previously revealed cases remain regression cases permanently. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `e8c8969165628f71ffbfc0efed3b4a1e14066ad01dff75611303f3395bb91b7f` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `32ab8891dc3190b9e96f2f6dc04841bbeecd863534cdeecf69a5cd0769c8b66b`.
- Review-prompt SHA-256 recorded by receipt: `fb70f9f0c4d03c5096166b3185470606201295df2a1d99c79f941fd2f621a650` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
