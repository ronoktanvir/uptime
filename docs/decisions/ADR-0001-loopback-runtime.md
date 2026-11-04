# ADR 0001 · loopback runtime

**Decision.** Use FastAPI and a static browser client in one loopback process with SQLite transactions. This is a local substitute for the proposed Next.js/Postgres deployment.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/01.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** Opus agreed but questioned the unverified isolation claim in the early packet. The Git worktree inventory and separate worker commits now verify isolation. Its warning about one local operator becoming mistaken for production identity remains a release limit. [Opus response, session and UTC timestamp](reviews/01.json).

**Verification.** tests/test_storage.py, tests/test_release_boundaries.py and tests/test_journey_api.py (restart, process exit before commit, nonce/tenant, concurrent transitions).

**Rollback and boundary.** Stop the local service and reopen a prior checkout against a copy of its matching database. Retain original state. Revisit for multi-process or third-party hosting.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
