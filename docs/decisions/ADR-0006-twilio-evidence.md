# ADR 0006 · twilio evidence

**Decision.** Use the dated April 9 API SLA, documented status intervals, product/plan applicability, affected monthly invoice fees, explicit exclusions and the filing clock.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/06.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** The reviewer warned about false precision from status feeds. The supported dedicated case uses labeled synthetic attestation plus the actual public clause. Internal telemetry is not a universal prerequisite. Unsupported throughput calculations stay unsupported; a missing required fee basis stays missing. [Opus response, session and UTC timestamp](reviews/06.json).

**Verification.** tests/test_twilio.py and fixtures/twilio/README.md. Verify continuity before calendar clipping, exact strict threshold, contracted fee exclusions, overlapping intervals, plans and missing evidence.

**Rollback and boundary.** Withdraw the rule version or keep new terms in shadow until supported. No real customer entitlement is inferred from this calibration.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
