# Independent before/after release gate

The gate executes immutable V3 and a selected V4 checkout with the same independent audit driver. A passing driver test suite is not a product release certificate. All 118 required observations must execute and pass for release; a missing browser or unverified baseline blocks approval. See [audit/RESULTS.md](audit/RESULTS.md) for the recorded runs and outstanding failures.

Owned files are `scripts/v4_audit_gate.py`, `tests/test_v4_audit*.py`, this document and `docs/v4/audit/`. Candidate application code, the independent oracle and blind holdouts remain untouched. The durable task directory receives handoff copies and commit identifiers. The migrated `NOTES-generalqa.md` was absent; the available `INTERFACES-V4-RICH.md`, current source and prior audited vectors supplied the protocol context. No provider API, private capture, customer files, external model or existing credential is used.

## Fixed observations and honest failure handling

The original 114-observation driver and its unmodified V3/V4 results are retained in [initial-baseline.json](audit/initial-baseline.json) and [initial-release.json](audit/initial-release.json). Revision 2 retains those observation IDs and adds four required controls: named authority acceptance/refusal, durable allocation identity/readback and serialized allocation contention. The fixed manifest requires exactly 118 unique IDs. Missing, duplicate or unexpected output cannot reduce that count or pass the release gate.

The gate recomputes assertion results from observed and independently specified expected values. It ignores probe pass flags. A failed financial probe retains completed observations and marks the unexecuted remainder UNAVAILABLE. An exception after the last observation still blocks. Diagnostics contain exception type and code location, never exception messages, capabilities or HTTP bodies.

Release requires an exact-V3 baseline with the same driver hashes and expected values. Altered baseline pass flags, stale driver versions, omitted observations and changed source during execution block certification. Each report includes the actual invocation, source commit and recursive product hash, fixture hashes, driver hashes, runtime/package versions, required system Chrome path/version and per-observation audit provenance. The `counts` field is derived from results, not accepted from the application.

## Protocol bridges and positive controls

V3 runs from a `git archive` of `18afaa6433284dc582d38c02b797dc4e688892f1`; no candidate modules are substituted. V4 runs the selected checkout's actual `create_app`, including its mounted routers. The bridge enrolls disposable synthetic named P-256 reviewer/viewer keys, enables the deployment approval gate, and signs the exact origin, path and body challenge. It implements signing independently of the candidate's client helper. Private keys, tokens and proofs stay in memory and temporary synthetic state.

The healthy reviewer must approve a real claim, and the same case ID and stage must read back. Wrong signatures, invalidated identities and a disabled deployment gate must refuse writes without changing the case. These are separate controls. The primary Jira ABA probe uses the same healthy reviewer, proves initial approve/activate success, and obtains a fresh cryptographic proof for every stale domain action. Its required stale-action response remains `409`; a wrong signer, obsolete subject or disabled gate cannot satisfy that assertion.

Some old fixture shortcuts are deliberately unsafe in V4. Their replacements preserve the audited financial expectations and attacks:

- Novel positive claims provision explicit scoped invoice fields and immutable hashes before seeding. The simulated counterparty independently receives matching account, invoice and minimized document identities. The expected award remains `$41.73`; missing-component and wrong-line-scope mutations still refuse recovery.
- Duplicate cases and private annotations enter through initial synthetic fixture intake. Post-seed SQL tampering cannot masquerade as successful business deduplication or outbound minimization. The privacy probe requires an actual dispatch before checking the captured packet.
- The known-maintenance test fixes the decision clock after the notice's recorded availability. A not-yet-available notice is not evidence of a prefiling exclusion defect.
- The one-cent settlement test uses actual persisted transitions. A rejected zero partial application must leave the posted credit at `$0.00` applied with no application ID.
- Jira good standing is an issuance condition. Timely filing retains `ELIGIBLE`, `$120.00`, `TIMELY` and `BLOCKED_ACCOUNT_STANDING`; V3's conflation remains a failing baseline observation. This explicit semantic correction replaces the old incorrect `J-good-standing` expectation. It does not edit a product oracle.
- Sub-cent entitlement comparison uses four decimal places so `0.001` and `0.0010` represent the same amount. Original UTC/pricing/tier expectations are unchanged.

The allocation bridge verifies an accepted `$80.00` application, duplicate idempotency, exact award/credit/bill/application/case IDs, restart readback and immutable historical readback. Two independent SQLite writers contend for one `$100.00` bill with `$80.00` grants. Exactly one must succeed, one must refuse, and persisted total/count must remain `$80.00`/one application. Wrong account/product and a predating bill must not apply.

The mounted vendor probe submits explicit synthetic source text, a separate customer overlay and independent positive/refusal cases through signed `/api/vendors` routes. It proves preactivation refusal, ACTIVE dispatch of `$120.00`, the same case in dashboard/readback, refusal after rollback and preservation of the historical case/version/timeline. No test router or compiler patch replaces the application.

## Browser requirements

Both phases require real system Chrome at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, Playwright, two bindable loopback listeners and permission to launch Chrome. There is no bundled-browser fallback or skip-pass. The managed worker currently cannot bind a loopback socket; those observations are UNAVAILABLE, not fixed.

The browser probe authenticates V3 by its real session URL and V4 through its real named-key sign-in form. A UI claim approval must succeed and read back on the same case. A second actual browser origin receives the host-scoped V3 cookie. The test attempts a browser sibling request and a capability replay with a forged allowed Origin, checks rejection and unchanged state, and keeps all raw capabilities out of reports. V4's signed action must succeed before replay refusal counts.

The same browser then completes simulated credit reconciliation and checks rendered receipt, credit, bill and application IDs against API readback. Security observations survive a later financial-UI failure. This browser implementation is not claimed validated until root executes it outside the nested socket sandbox.

## Exact operator commands

Runtime used by the worker: `/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python`. Its installed package versions and Chrome metadata are recorded in each report. Root should execute the commands below outside the nested sandbox, using a frozen driver revision for both phases. The baseline and release commands must run sequentially even if baseline exits `2`; do not join them with `&&`. Use new report filenames for subsequent runs so prior evidence remains intact.

```sh
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python /Users/ronoktanvir/.local/share/uptime-engineering/worktrees/qa/scripts/v4_audit_gate.py --phase baseline --source /Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4 --report /Users/ronoktanvir/.local/share/uptime-engineering/tasks/qa-baseline-browser-v2.json
```

```sh
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python /Users/ronoktanvir/.local/share/uptime-engineering/worktrees/qa/scripts/v4_audit_gate.py --phase release --source /Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4 --before /Users/ronoktanvir/.local/share/uptime-engineering/tasks/qa-baseline-browser-v2.json --report /Users/ronoktanvir/.local/share/uptime-engineering/tasks/qa-release-browser-v2.json
```

Driver verification, from the durable assigned worktree:

```sh
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python -m pytest tests/test_v4_audit*.py -q
```

Baseline exit `0` means all before observations ran, including expected defect failures; baseline can never authorize release. Baseline exit `2` means at least one observation was unavailable. Release exit `0` alone certifies the complete gate; any other release result blocks. After an integration merge, the integration owner must also run the repository-required `uv run --locked pytest`.
