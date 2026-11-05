# Independent QA protocol, revision 2

Owner: durable `worktrees/qa`; candidate and independent oracle are read-only.
Baseline is exact V3 `18afaa6433284dc582d38c02b797dc4e688892f1` materialized with git archive. Release uses the requested source checkout in a fresh interpreter. The initial durable reports preserve the original v1 driver results before bridging.

The v2 report will retain the fixed required observation manifest, observed and independently specified expected values, PASS/FAIL/UNAVAILABLE, source and driver content hashes, interpreter/package/browser versions, exact invocation, baseline transitions, and safe exception type/location. Every missing observation blocks release. No browser fallback, skip-pass, candidate-supplied pass count, or baseline-supplied expectation is permitted.

V4 writes use a freshly enrolled synthetic named P-256 reviewer, exact loopback origin, approvals enabled, and a new signature per action. ABA lifecycle tests retain the same named reviewer and issue fresh proofs for stale domain actions; wrong signer, obsolete identity and a disabled deployment gate cannot stand in for stale-action rejection. Financial bridging adds the durable allocation ledger and staged Jira filing/issuance semantics. Unsafe old positive fixtures will be explicitly repaired with scoped synthetic evidence; the original V3 counterexample remains frozen.

Required browser runtime: Python with the locked application dependencies, pytest, Playwright and cryptography; system Google Chrome at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; permission to bind two loopback listeners and launch Chrome. Root must rerun both phases outside the nested socket sandbox. Missing runtime is UNAVAILABLE and release remains false.

Migrated `tasks/NOTES-generalqa.md` is absent. No blind holdout content, private capture, credentials, external model or live provider is used. Native main integration currently equals assigned source `e120dcd`; recheck after root integrates workbench changes.
