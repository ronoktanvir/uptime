# ADR 0011 · local policy

**Decision.** Keep assisted as default and support observe plus opt-in per-tenant simulator dispatch under a reviewer-configured cap. Only a newly approved and attested initial packet can dispatch automatically.

**Alternatives, lead recommendation, cost and risk at decision time.** The [sanitized packet](packets/11.md) records the prior position, alternative and acceptance targets before this review.

**Independent review and resolution.** Opus preferred this over indiscriminate automation and cautioned against low-value but uncertain claims. Replay alone enables the policy; no automated supplements, settlement writes, promotion or real transport. The independent audit additionally found and fixed a duplicate-approval-after-policy-change defect. [Opus response, session and UTC timestamp](reviews/11.json).

**Verification.** tests/test_release_boundaries.py, test_disputes.py and test_storage.py; cap boundary at 99.99 vs 100.00, duplicate approval under changed policy, observe, foreign/viewer and restart checks.

**Rollback and boundary.** Change back to observe or assisted; policy revisions persist. Do not export this single-process policy to distributed workers without new concurrency controls.

Owner: integration lead. Scope: reversible local prototype; advisory acceptance provides no external or commercial authorization.
