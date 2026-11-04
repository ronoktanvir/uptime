# ADR 0010 · local identity

**Decision.** Use out-of-band local reviewer/viewer capabilities, short-lived opaque cookies, fixed tenant and origin/host/header checks. Human actions remain explicit; scripted approvals only exist in temporary rehearsal DBs.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/10.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** Opus warned about confused-deputy risk if used as real SSO, replayed tokens and leaked links. The launcher binds only to 127.0.0.1, suppresses access logs, requires a secret and separates recording sessions. No browser role selector can mint a privileged identity. [Opus response, session and UTC timestamp](reviews/10.json).

**Verification.** tests/test_journey_api.py and test_release_boundaries.py cover spoofed identity, foreign and expired sessions, cross-site writes, DNS rebinding, viewer actions, unsupported stages and crashes.

**Rollback and boundary.** Stop process, close bootstrap links and expire sessions. Require organizational identity, dual control and protected audit storage before any production deployment.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
