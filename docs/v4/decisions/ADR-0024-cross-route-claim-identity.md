# ADR-0024: Cross route claim identity

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Reserve one monthly remedy identity across routes and retain immutable filing/supplement receipts; agreement version is provenance, not a new right to file.

Route-local uniqueness allows duplicates; banning repeated demo account names blocks valid work without solving identity. A universal unscoped key suppresses legitimate claims. The chosen scoped monthly key deliberately does not support arbitrary per-invoice remedies.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/24-cross-route-claim-identity.json](reviews/24-cross-route-claim-identity.json); its sanitized input is [packets/24-cross-route-claim-identity.md](packets/24-cross-route-claim-identity.md). Receipt time: `2026-11-05T00:20:49.726597+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `8a260828-4919-4bdf-b424-551ddfe42de1`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus objects that agreement version in the key permits duplicate filing after a harmless amendment, proposes lineage/controlling terms, and requires outbox treatment of unknown sends plus migration conflict handling.

**Root position and reconciliation:** Accept the version objection. Actual key uses agreement lineage and omits version, invoice, incident, component and case/route. It is intentionally conservative for one monthly remedy; changed terms do not automatically authorize a second claim. A generalized per-invoice or real external-send scheme remains outside proof. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

claim_identity._economic validates but excludes agreement_version. Immutable primary key is obligation plus initial/supplement; reservations reject cross-route ownership and require the original receipt for supplements. Backfill refuses unknown historical remedy.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/claim_identity.py](../../../uptime/claim_identity.py)
- [uptime/disputes.py](../../../uptime/disputes.py)
- [uptime/correspondence.py](../../../uptime/correspondence.py)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_claim_identity.py tests/test_claim_identity_migration.py tests/test_cross_claims.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** The same obligation filed through two routes, a harmless amendment permitting a second initial claim, a new account/month incorrectly blocked, or an unknown send reservation released for blind retry falsifies the decision.

## Versioned rollback

Disable dispatch, preserve all reservations and outbox/receipt state, quarantine backfill collisions and reconcile unknown delivery manually. Revert compatible callers only; deleting uniqueness history risks duplicate filing. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `79fa2176cffe78636b2368feaa78218a7e6d6db5e1837c6820f26b9bea301d8c` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `cad5b1ca4f259665c157af7651b997413a482f4353b56578996553e80ef1972d`.
- Review-prompt SHA-256 recorded by receipt: `8382c322039c849d502be1f1c7bd990de779bebcfe24a15f349c123e1f8ced29` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
