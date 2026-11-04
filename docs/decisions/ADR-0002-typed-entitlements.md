# ADR 0002 · typed entitlements

**Decision.** Use four traced outcomes, immutable source-cited evaluations, Decimal amounts and explicit USD support for claims. Preserve native currency on observational provider records.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/02.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** We agree with the reviewer's fail-closed approach. Stale data is an evidence qualifier rather than a fifth financial verdict. We disagree with deferring equal W3/W4 staffing: the team explicitly required it and the CP1 fixtures let both proceed independently. [Opus response, session and UTC timestamp](reviews/02.json).

**Verification.** tests/test_contracts.py, test_twilio.py, test_pricing*.py, test_evidence*.py and test_release_boundaries.py; changes in template/source are exercised in test_onboarding_lifecycle.py.

**Rollback and boundary.** Reject an unsupported field/version and retain the last approved version. Review new currency and vendor rules before widening coverage.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
