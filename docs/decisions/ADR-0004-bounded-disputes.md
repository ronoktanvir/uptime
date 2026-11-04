# ADR 0004 · bounded disputes

**Decision.** Keep independent claimant and simulator data, contract-grounded packet evaluation, precommitted oracle and terminal stop/escalation states. No external submission connector.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/04.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** We agree that a second implementation can share its author's mistakes. The oracle predates both implementations. Mutated decisions, unavailable evidence, duplicate replies, corrupted facts, expiry and partial awards exercise their separation. This verifies the fixture contract, not real vendor acceptance rates. [Opus response, session and UTC timestamp](reviews/04.json).

**Verification.** tests/test_disputes.py; fixtures/disputes/oracle and four replay traces. Commit a01e9f8 froze the oracle before the simulator and claimant.

**Rollback and boundary.** Set OBSERVE to stop local actions. Use a prior checkout and a separate fixture DB to replay. Live vendor communication or settlement needs separate human authorization.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
