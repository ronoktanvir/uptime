# Test changes — limited local review permission

No existing test function or assertion changed. The original local release, native authorization, financial correctness and scripted-history tests remain intact. The helper gains an explicit, narrowly constrained permission path; its default still uses the original release gate.

Two new files add 83 parametrized cases:

| File | Cases | Purpose |
|---|---:|---|
| `tests/test_local_review_exception.py` | 14 | Unsigned preparation without key use or owner approval; both authorization channels and domain separation; the exact signed lifecycle; source, receipt, candidate and key tampering; copied/restored workspaces; durable revocation; clock rollback; audit failure; safe CLI output. |
| `tests/test_local_review_exception_disputes.py` | 69 | An allowed adapter action first succeeds in the fixture, then financial/dispute/native challenges and transplanted proofs fail without changed domain rows or authority audit. Includes source/version changes, missing owner approval, expiry, terminal rollback, Git verification errors and 12 request-representation controls. |

The exact new function names are preserved in those files. The table describes new coverage, not changes to previously accepted expectations. All keys, owner approvals and grant activations in these tests are disposable fixtures; no actual Ronok action or permission is demonstrated.

Focused results: 14 passed, 1 warning in 2.90 seconds; independent negative suite 69 passed, 1 warning in 18.43 seconds. The broader helper/Northwind check passed 63 tests with one warning in 62.46 seconds before the last audit-failure control was added; the final 14-case run includes that added case. During implementation review, a Git source-check failure could escape as an exception; the handler was corrected and its dedicated denial regression passes. No known failure is reclassified as successful human review.

The mandatory merged `uv run --locked pytest` result, exact source commit and unsigned-proposal status are recorded in [verification](evidence/local-review-88/verification.json). The exception remains inactive until the concrete human review and its separate approval/signing steps.
