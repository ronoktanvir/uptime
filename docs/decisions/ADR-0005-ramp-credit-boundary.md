# ADR 0005 · ramp credit boundary

**Decision.** Pin Ramp to the demo origin, inspect real scopes first and restrict any optional write to one uniquely tagged, journaled draft. Keep vendor award, provider credit and bill application distinct.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/05.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** Opus advised against writes until scope and draft safety were observed. The exact scope was absent. We did not make a mutation. Its same-ID/currency/tag tests remain valid for the fixture path. An empty credit endpoint is evidence of a read, not a reconciliation success. [Opus response, session and UTC timestamp](reviews/05.json).

**Verification.** tests/test_ramp.py, test_reconciliation.py and fixtures/ramp/verified.json; real paid + pending ID reads, no vendor credits. Later stage-origin hardening is in ADR-0013.

**Rollback and boundary.** Disable the sandbox connector; replay fixtures. Preserve the local idempotency journal if a future authorized write is interrupted. No automatic retry of an ambiguous write.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
