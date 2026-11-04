# ADR 0007 · dated pricing

**Decision.** Resolve the effective signed version at service time and calculate explicitly defined graduated tiers. Record line overcharges and undercharges separately; never alter provider payment state.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/07.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** Opus flagged cumulative-tier ambiguity across amendments. The synthetic contract defines line allocation and cent rounding; unsupported cumulative schemes and ambiguous rate-spanning lines fail closed. The live pending bill is an evidence gap rather than an opportunity. [Opus response, session and UTC timestamp](reviews/07.json).

**Verification.** tests/test_pricing.py, test_pricing_binding.py, test_pricing_invariants.py; 2,001 quantity checks in the invariants sweep and a separate retrospective case.

**Rollback and boundary.** Disable the synthetic rule or select an earlier agreement version for an explicitly dated replay. Preserve both provider and fixture evidence.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
