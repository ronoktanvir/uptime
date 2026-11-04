# ADR 0012 · additional obligations

**Decision.** Add narrow synthetic annual earned-rebate, receipt-clock and negative parity examples after W3/W4 independent completion. Use explicit threshold, return scope and supplied business calendar.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/12.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** The reviewer cautioned that edge fixtures are not general coverage of negotiated agreements. The UI labels them as comparison cases; conditional results and missing calendars cannot join the primary recovery ledger. Parity without a verified comparator method has no numeric entitlement. [Opus response, session and UTC timestamp](reviews/12.json).

**Verification.** tests/test_other_obligations.py; inclusive USD 100,000 net spend, prior USD 500 credit, notice cutoff equality, closures and missing calendar. The source is the synthetic agreement under fixtures/other_obligations.

**Rollback and boundary.** Drop comparison fixtures from new seeds, retain past snapshots. Do not imply real rebates, legal notice delivery or privileged comparative pricing.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
