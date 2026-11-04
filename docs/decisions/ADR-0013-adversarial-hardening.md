# ADR 0013 · adversarial hardening

**Decision.** Require the fixed workspace at session resolution, render provider native amounts/nulls, preserve unresolved dispute state while settling confirmed value, reject mismatched settlement source roles, bound HTTP bodies, guard model origins and suppress redispatch on old approvals.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/13.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** Opus challenged whether earlier green tests were achieved only by changing inputs. We preserved the original negative fixtures and added executable post-fix reproductions. The duplicate-effective-date pricing fixture now isolates ambiguous precedence; a separate test still explicitly rejects late signatures. The independent worker reran the foreign tenant, EUR, partial award and retry attacks against the repaired implementation. [Opus response, session and UTC timestamp](reviews/13.json).

**Verification.** tests/test_release_boundaries.py, test_reconciliation.py, test_intelligence.py and test_journey_api.py. Sources for awarded/posted/applied are projected separately. A simulated award plus genuinely linked sandbox data is never actual customer recovery.

**Rollback and boundary.** Remain in replay/observe when an origin, amount, identity or scope is uncertain. Preserve the earlier immutable record; forbid any production dispatch. Revisit on new connectors or deployment expansion.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
