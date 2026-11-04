# W6 pricing integration

`uptime.pricing.demo_cases() -> list[dict]` supplies complete CP1 case details,
with stable `price-` IDs, source tags, traces, clause references, evidence,
timeline, financials and empty action lists. The service owner can append these
cases to its read models without exposing caller-supplied financial inputs.
All default cases are `SYNTHETIC_CUSTOMER` + `DETERMINISTIC_REPLAY`.

`evaluate_price(agreement: Agreement, invoice: Invoice) -> PricingResult` is a
pure calculation. `PricingResult.evaluation` uses the frozen shared
`EvaluationResult` interface. `ELIGIBLE` means a provisional, evidenced pricing
discrepancy under these fictional terms; it does not establish a real claim,
prevented payment or recovered money. `overcharge` and `undercharge` are separate
Decimals; `LineFinding.delta` preserves direction. Missing or unsupported
evidence suppresses the entire invoice's aggregate value. No partial claim is
silently emitted. The original immutable invoice/payment status is preserved.

The fictional signatures in `agreement.json` are test evidence only. They are
not cryptographic verification or an assertion that real parties signed. The
agreement explicitly defines completed whole-unit service allocations,
half-open performance intervals, graduated upper-inclusive tiers, separate tax
exclusion and per-line cent rounding. Those fixture terms make the arithmetic
reviewable without inferring actual commercial terms. Monthly cumulative,
volume/all-unit, ambiguous boundary, cross-amendment unallocated, retroactively
signed, FX, tax-inclusive and future-performance billing rules fail closed.
Tax arithmetic is reconciled to the invoice total; tax correctness is outside
the price finding and is never adjudicated.

The October example bills $27,500 for 1,500 jobs; amended tiers allow
1,000 × $15 + 500 × $10 = $20,000. Its $7,500 discrepancy excludes $2,500 of
premium support and any itemized taxes. September performance allows $27,500
under the original version, regardless of a November invoice date. The paid
October example is a retrospective review candidate; claimed, awarded,
prevented, recovered and applied amounts remain zero.

## Optional provider binding (trusted W1 adapter only)

`bind_sandbox_bill(provider: ProviderBill, mapping: Invoice) -> Invoice` binds
an authenticated, verified sandbox read to a **separate synthetic allocation**.
The adapter must supply the exact provider bill ID, vendor ID, decimal gross
amount, USD currency, normalized `pending`/`paid` status, observation timestamp,
verification artifact reference, `LIVE_RAMP_SANDBOX` tag and exact sandbox API
origin. A `verified=True` flag or source label is not independent verification;
the trusted W1 reader owns that attestation. W6 does not perform live reads.

The synthetic mapping must explicitly carry the same bill ID, provider vendor
ID, total, currency and status. Its own customer/vendor identities describe
fictional contract parties; they do not establish a relationship with the
provider vendor. Itemized synthetic net plus separate tax must equal the exact
provider amount. No rescaling, substitutions or automatic use of the $30,000
demo invoice occurs. If the provider supplies a complete line set, line IDs and
every available net/tax/product/quantity/unit/performance-date field must agree.
Unavailable provider fields remain unavailable; synthetic mapping does not
upgrade their provenance. Conflicts raise `PricingInputError` with an outcome;
directly constructing a bound `Invoice` cannot bypass evaluator revalidation.

Successful bound evaluations carry `LIVE_RAMP_SANDBOX` and
`SYNTHETIC_CUSTOMER` separately. The live tag applies to the bill read, not to
the agreement or inferred service details. No default demo is live-bound.
Provider tests use mocked attestations, never actual live-read evidence.
The service owner must serialize bound results with field-level evidence in
the same manner; it must not replace the default replay cases' source tags.

## Governance and tests

This implements ADR 07's reviewed immutable performance-date resolution,
bidirectional discrepancies, fail-closed allocation, and payment immutability.
The intentionally narrow tier and tax semantics come from explicit synthetic
fixture terms. Supporting real commercial scope, cumulative tier allocation,
retroactive signatures, taxes or additional currencies requires a new decision
by the central lead. No provider APIs, transport, credential access, claims,
payment changes, shared interfaces or other workers' files are modified.

From this worktree, run the existing environment without installing packages:

```sh
../../../outputs/uptime/.venv/bin/python -m pytest
```

The pricing tests cover the $7,500 examples, exact tier and amendment boundaries,
timezones, historical rates, explicit splits, both discrepancy directions,
immutable inputs, cent rounding, missing evidence, unknown product scope,
currency/tax/signature rejection and every available provider field conflict.

### Worker validation result

The standard-library fallback passed all five invariant tests:

```sh
python3 -m unittest discover -s tests -p test_pricing_invariants.py -v
```

These exercise 2,001 quantities, five timezone representations of the amendment
boundary, both discrepancy directions, immutable payment status, missing
evidence suppression and conflicting provider bindings. Syntax and whitespace
checks passed for all eight owned files. The demo returned its five expected
outcome/amount pairs, including both $7,500 cases.

The requested existing-venv `python -m pytest` was attempted from this worktree
but stalled before collection while reading installed pytest/dependency files.
Bounded diagnostics confirmed import-time file-read stalls; plugin-autoload and
bytecode workarounds did not resolve them. Pending runs were stopped; no
packages were installed or downloaded. The two pytest-specific test modules
remain unverified and need the parent's full-suite run after integration.

Git staging failed because the sandbox denied creating the parent repository's
worktree `index.lock`. No commit was created; all eight owned files are left in
the worktree for the parent. Existing unrelated `config/` files were untouched.
