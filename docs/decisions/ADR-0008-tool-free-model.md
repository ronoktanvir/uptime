# ADR 0008 · tool free model

**Decision.** Only curated public inputs reach a tool-free authenticated model. Validate structured output against allowed slots and cited source IDs. Render read-only explanation plans from the current local case.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/08.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** We accepted the dissent on classification: the primary Twilio model input is pinned byte-for-byte; the Atlassian extraction checks approved normalized source text before a refresh. A changed source needs explicit review. There is no arbitrary user prompt forwarded to a provider. [Opus response, session and UTC timestamp](reviews/08.json).

**Verification.** tests/test_intelligence.py and test_release_boundaries.py; fixtures/model/verified_plan.json and fixtures/onboarding/extraction.json identify real model sessions. Tool suggestion, wrong amount and unknown refs fail verification.

**Rollback and boundary.** Serve previously verified offline artifacts or disable guide generation. A different provider, new source class or confidential data requires a separate review.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
