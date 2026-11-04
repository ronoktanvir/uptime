# ADR 0003 · governed onboarding

**Decision.** Generate a public declarative candidate, combine it with a separate tenant overlay, run generated tests and independent gold checks, then shadow, approve and activate locally.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/03.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** The cheaper hardcoded plug-in would not meet the requested generation demonstration. We accepted the reviewer's stronger requirement to invalidate a changed approval basis and test rollback across versions. Coverage is restricted to supported Jira experiences, with no inferred holiday calendar. [Opus response, session and UTC timestamp](reviews/03.json).

**Verification.** tests/test_onboarding_lifecycle.py and test_onboarding_rules.py; fixtures/onboarding/extraction.json records the separate real model run. Fourteen generated boundaries, 23 term checks, 18 labeled shadow cases.

**Rollback and boundary.** Roll back to a prior compatible local version or revoke. Never reinterpret old receipts under new terms. Production promotion requires a real customer authority.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
