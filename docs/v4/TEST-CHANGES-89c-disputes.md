# Test changes, W4 follow-up 89c (D03-A residual on the legacy Twilio dispute route)

Branch `work/dispute-wire-identity-89c`, based on `work/identity-pricing-89` at `6ebaffe`. That commit is the first to contain `uptime/source_identity.py`.

## Change

The legacy `disputes_wire.Ticket.account` previously accepted any printable value without surrounding whitespace, for example an em dash, so it could accept identities other routes refuse. It now uses the D03-A domain `source-identity/1` at three layers:
- **Claimant eligibility** (`disputes_claimant.eligibility`): `INSUFFICIENT_EVIDENCE`.
- **Counterparty** (`disputes_vendor.decide`): `CONTESTED_SCOPE`.
- **`Ticket` construction**: `ValueError`. The value is refused, never rewritten.

Stored legacy accounts are restricted IDs, a strict subset, so ticket digests and obligation keys are unchanged.

## Existing tests

None edited. Run:

```sh
uv run --locked --offline pytest -q --basetemp=<unique> -o tmp_path_retention_policy=failed \
  tests/test_disputes*.py tests/test_local_review_exception_disputes.py tests/test_cross_claims.py tests/test_source_identity*.py
```

Result: **239 passed, 1 warning, 30.03s.** This includes the new `tests/test_disputes_identity_89c.py`, which had 12 passed on its first run.

## Frozen artifacts

- `fixtures/disputes/oracle/v1.json` SHA-256 `f74f7409…23f8` and `v2.json` `7c03ad35…8041` are unchanged and match their pins.
- `python -m uptime.disputes_replay dispute-cure|dispute-denial|dispute-review|dispute-partial` regenerates output byte-identical to the committed `fixtures/disputes/traces/*.json`.

## Addendum: vendor and service names (D03 extended, relayed 2026-11-09)

`Ticket.__post_init__` and the counterparty now also apply `source-identity/1` to `vendor` and `product`.

The claimant's `preflight` already requires the exact covered service name `Twilio Messaging API` and returns `UNSUPPORTED` otherwise. So it got no new check: a first-draft claimant check was redundant and was reverted before commit.

My own first draft of the new test called a non-existent `eligibility` function (`ImportError`, 1 failed, 20 passed). It now asserts the existing `preflight` `UNSUPPORTED` outcome.

Run on the final source: **248 passed, 1 warning, 61.89s** (same command as above). All four replay traces are byte-identical, and no existing test was edited.
