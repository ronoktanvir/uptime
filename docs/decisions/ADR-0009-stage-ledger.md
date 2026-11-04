# ADR 0009 · stage ledger

**Decision.** Display one price exposure and one named dispute history. Keep estimate, filed, awarded, recorded and applied values distinct and non-additive. Keep comparative cases out of portfolio arithmetic.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/09.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** Opus noted that honest zero application may look less dramatic. We kept the separate stages and exposed a partial application for the film. This supports a factual explanation without claiming customer revenue. [Opus response, session and UTC timestamp](reviews/09.json).

**Verification.** tests/test_journey_api.py, test_reconciliation.py and test_release_boundaries.py. Live sandbox records and simulated application are visibly distinguished.

**Rollback and boundary.** When any stage loses evidence, show unavailable and keep existing referenced history. Never replace it with a positive fixture value on the same live measure.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
