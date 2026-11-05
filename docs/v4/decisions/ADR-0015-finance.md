# ADR-0015: Finance

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Compare performance and amendment instants in UTC, retain contract calendar semantics explicitly, reject conflicting identifiers, and calculate exact money before contractual rounding.

Blanket UTC calendars are simpler but can shift rights at local month/day boundaries. Trimming or deduplicating financial identifiers is convenient but can merge distinct charges. Strict scope and precision rejection increases unresolved cases while preserving financial integrity.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/15-finance.json](reviews/15-finance.json); its sanitized input is [packets/15-finance.md](packets/15-finance.md). Receipt time: `2026-11-05T00:20:16.123910+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `52ecc667-a99d-4d47-a4ad-a28bdeefd606`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus supports hybrid time handling but asks who classifies each time field, notes absent tzdata/version evidence, and requires equal-instant, DST, alias, missing-document and ambient-precision falsifiers.

**Root position and reconciliation:** The packet’s numerical probes motivate correction but are not proof of root cause or closure. Accept the demand for field-specific semantics; no conclusion about all contracts or currencies follows from supported USD examples. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

pricing._instant and dated version selection compare aware instants; agreement validation requires ordered signed versions and exact citations. Allocation settlement is explicitly USD cents. Audit main-release-v2 reports its financial observations passed at its own earlier pinned revision, not at every subsequent build.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/pricing.py](../../../uptime/pricing.py)
- [uptime/other_obligations.py](../../../uptime/other_obligations.py)
- [uptime/twilio.py](../../../uptime/twilio.py)

Audit: [durable audit results](../audit/RESULTS.md), especially its source pin, unavailable browser observations and failed release flags. This report does not certify the later inspected main revision.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_financial_v4.py tests/test_pricing_invariants.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Equal instants yielding different entitlement, padded IDs increasing totals, missing controlling documents permitting filing, or precision-dependent output falsifies the decision. Unspecified settlement precision and unverified calendar semantics remain unsupported rather than guessed.

## Versioned rollback

Suspend affected evaluator dispatch, retain original inputs/traces, restore the compatible version and append reevaluation differences. Do not rewrite historical amounts or adopt a new rounding rule silently. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `87f85473d2bf369c40774a05e672d45cfbbcf1eb1f4f35372bf3b4d7b83500b0` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `cb1272178ee27dc1d470f38f9f4dee7f909573d902216f0d139ae4cc56392b8d`.
- Review-prompt SHA-256 recorded by receipt: `75235f8fc2902afe984783a3966fbae7d286d01f90201017ee4fcb6f52b37bb2` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
