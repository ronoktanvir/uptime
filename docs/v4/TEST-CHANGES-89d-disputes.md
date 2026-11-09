# Test changes, W4 follow-up 89d: narrow month-coverage rule (D07, W5 F3 option A)

Branch `work/dispute-coverage-89d`, based on `work/dispute-intake-scope-89b` at `99a603c`.

**Status:** prepared for the overview session's Q1 choice. It is not handed over for merge until that choice is recorded.

## Change

In the ordinary Twilio profile (`uptime/correspondence_rules.assess`), a result of "availability at or above the threshold" now becomes `INSUFFICIENT_EVIDENCE` when both of these hold:
- the result was derived from one provisioned status record, with no signed complete-month coverage report;
- no substantiated exclusion applies.

The missing item names the report.

Unchanged:
- **Breach.** A breach established from that lower bound still yields the fixed 10% credit (`uptime/twilio.py:21`, `:405–413`). Unseen extra downtime cannot change that amount.
- **Exclusions.** Maintenance and customer exclusions are unchanged.
- **Trace.** The `month_coverage_basis` detail now states this.

## Existing tests

None edited, and none moved. Command:

```sh
uv run --locked --offline pytest -q --basetemp=<unique> -o tmp_path_retention_policy=failed \
  tests/test_correspondence*.py tests/test_disputes*.py tests/test_northwind*.py tests/test_cross_claims.py \
  tests/test_v4_routes_integration.py tests/test_portfolio_v4.py tests/test_ramp_award_claim_integration.py
```

Result before adding the new tests: **1004 passed, 1 warning, 270.51s.** For comparison, the full F3 rule (report required before any outcome), tried as a reverted experiment, failed 168 cases across 112 test functions.

## New tests

`tests/test_correspondence_month_coverage_89d.py`, 4 tests: **4 passed.**

Mutation check: with the rule removed, `test_target_met_from_one_status_record_is_missing_evidence` fails (1 failed, 3 passed).
