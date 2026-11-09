# W5 handoff — evidence and source custody

**Branch** `work/evidence-custody-90` (base `03b372e`). **All 14 W5 commits are merged** into `work/integration-90`; the latest integration head checked here is `e10d95d`. **Integration round 6** (`3f60647`, fresh clone) contains every W5 code commit: **4,664 passed, 1 warning in 322.63 s**, with all 56 W5 tests in the log ([receipt](evidence/integration-90/verification-3f60647.json)). Written November 9, 2026. Owner: W5 session `gen5`.

## Commits

| Commit | Kind | What it does |
|:---|:---|:---|
| `a924aae` | feat | Signed source grant refuses evidence outside its granted month (decision 91) |
| `5b02d61` | docs | Decision 91 packet, Opus critique, ADR, support matrix, findings probe and receipts |
| `dcec513` | docs | Owner dispositions for findings F1–F9 |
| `6d3536f` | feat | Twilio's public status page as the first real evidence source (decision 91a) |
| `9eafdf5` | test | Harness-hosted rehearsal script for the public status source |
| `8d3a54d` | docs | Matrix aligned with D07; ADR 91a; live public capture receipt |
| `2c0073f` | docs | F5 reviewed-binding decision and D10 recorded |
| `3a0e32f` | docs | Source-intake runbook: time rule and public status procedure |
| `7799f2e` | feat | Read-only audit that stored citations re-slice from their exact source |
| `df16d9d` | docs | Custody audit receipt for the demo workspaces |
| `fb093e4` | docs | Freshness position for dated signed observations (no cutoff added) |
| `7373318` | test | Signed-path acceptance controls for wrong customer, period, stale, tampered and reused records |
| `ab3f9e3` | docs | Acceptance receipt on the merged head; wording "intake verified, release gate pending" |
| `b073f68` | fix | Status source refuses a grant without incident or component (D04-C compatibility) |

## Files

New code: `uptime/evidence_applicability.py`, `uptime/evidence_status_source.py`, `uptime/evidence_custody.py`; `scripts/deliver_public_status.py`, `scripts/rehearse_public_status.py`, `scripts/audit_document_custody.py`, `scripts/probe_evidence_findings_91.py`. Changed code: `uptime/source_config.py` (one call in `event_in_scope`), `scripts/deliver_evidence.py` (names the refusal before signing).

New tests: `test_evidence_applicability_91.py` (23), `test_evidence_status_source_91a.py` (17), `test_evidence_custody_91.py` (9), `test_evidence_acceptance_91.py` (7).

Docs: [ADR 91](decisions/ADR-0091-evidence-temporal-applicability.md), [ADR 91a](decisions/ADR-0091a-public-status-source.md), packets and reviews 91/91a, [support matrix](EVIDENCE-SUPPORT-MATRIX-91.md), [test ledger](TEST-CHANGES-evidence-custody-90.md), [source-intake runbook](SOURCE-INTAKE.md) (appended), receipts under [evidence/evidence-custody-90](evidence/evidence-custody-90/).

Changed by other owners in W5 files, reviewed here: agent1's D04-C commit `e29fa3a` made the agreed `event_in_scope` hunk, so a component-less scope adds no resource constraint. It also dropped the Twilio `region` from three W5 test scopes and gave telemetry rows a literal region. I approved the code hunk and its conditions beforehand and reviewed the test-input changes for this handoff: no W5 assertion is weakened, because no W5 test relied on a region mismatch. agent1 added 8 W5-labelled cases in `tests/test_source_config_d04c.py`.

## Behavior

1. **Time applicability at the signed grant.**
   - A record whose measured time cannot belong to the granted month is refused with HTTP 403 before storage.
   - Short records are compared with the UTC month widened 14 hours each side.
   - A period report crossing the month boundary must keep more than 14 hours inside it.
   - A complete report cannot be observed before its period ends.
   - The intake desk (W4) now applies the same rule and the nested-scope check on every channel.
2. **One real evidence source.**
   - One verified Twilio public snapshot plus one chosen incident becomes one signed `status` record for an exact enrolled grant.
   - It checks the official origin, snapshot freshness, the granted vendor, incident and component, the published start and resolution, chronology and the month.
   - It never states customer impact, fees or month coverage.
   - Status: **intake verified with a live public capture; release gate pending.**
3. **Document custody audit.** Re-slices every stored adapter citation from the stored source text and checks document and quote hashes. It opens the database read-only (SQLite immutable mode). Demo workspaces: 77 of 77 citations across 5 adapter versions trace exactly. That shows the words are at the offsets, not that the interpretation is right.
4. **Support matrix** aligned with D07: exact text imports plus overlays, USD, calendar months, no PDF; findings register for other owners.

## Tests and actual results

- Round 6 full suite (`3f60647`, fresh clone, integration owner): **4,664 passed, 1 warning in 322.63 s**; 104 JavaScript checks.
- Merged-head acceptance (`23805c9`, detached checkout plus the acceptance file): **219 passed, 1 warning in 183.94 s** ([receipt](evidence/evidence-custody-90/acceptance-merged-91.json)).
- Branch focused run at `a924aae` (17 files, including all Northwind suites): **401 passed, 1 warning in 328.72 s** ([receipt](evidence/evidence-custody-90/verification-91.json)).
- Live public run, November 9 at 12:26:26 UTC: 50 incidents; incident `fm5fk85h6glc` was delivered by the real signed CLI over a loopback socket; the retry returned the identical receipt; the claim stayed `INSUFFICIENT_EVIDENCE` with a null amount ([receipt](evidence/evidence-custody-90/public-status-live-91a.json)).
- Preserved failures, listed in the test ledger: two failed intermediate runs and one flaw found by the Opus critique during decision 91, and one failed run during 91a. No existing test was edited by W5.

## Decisions

| ID | Choice | Provenance |
|:---|:---|:---|
| D07 | Narrow published matrix; one real evidence source; no PDF | **Ronok's own**, relayed by his overview session and recorded by the integration owner |
| D06 | Humans gate judgment | Ronok's own, relayed |
| D10 | Public-only data to Claude; private overlays and captures stay local | Ronok's own, relayed. Both W5 critique packets contained only public or authored data |
| D11 | Stay local and loopback | Ronok's own, relayed |
| D14 | Mandatory Opus critique no longer required | Ronok's own, relayed. Both W5 critiques predate it |
| D03-A, D04-C | Exact bounded source identity; server-selected scope variants | Ronok's own, relayed by the integration owner |
| F5 | Require a reviewed agreement binding | Ronok's own, relayed |
| F3 | Narrow option A: require a complete-month report before concluding the target was met; flat 10% eligible amount unchanged; full F3 deferred | **Delegated**: chosen by the overview session at 04:28 PST under Ronok's authorization to pick recommended defaults, not Ronok's personal decision |
| 91 | Refuse out-of-period evidence at the grant | W5 lead decision; actual Opus 5.5 critique, session `9a4d8b82-a28d-4b00-9a08-bb01ff014921`. It found a UTC−12 flaw, which was fixed; disagreements are recorded |
| 91a | Twilio public status as the real source | W5 lead decision within D07; actual Opus 5.5 critique, session `6e0ce0dd-8e29-41c8-9da3-c2dec50de3b2`. Adopted its "intake verified" label; one disagreement is recorded |

None of these decisions reached this session directly from Ronok; all came through the overview session or the integration owner.

## Findings routed to other owners

| ID | Status on `e10d95d` |
|:---|:---|
| F1, F2 | **Landed** (W4): the desk applies the time rule and nested-scope check; out-of-scope deliveries go to a contradicting-deliveries list |
| F3 | **Landed, narrow** (W4, delegated choice above); trace labels `month_coverage_basis` |
| F4, F6 | Accepted (W3); batched into one `vendor_terms` semantics revision; not verified as landed |
| F5 | **Landed** (`448fe38`, agent1) |
| F7a | Accepted as an open W0 item: an audit stream of refused deliveries; not implemented |
| F7b | W4 design for retracting a signed record; must fit the D06 action matrix, which is not yet written |
| F8 | **Landed** (W4): `status_origin` names the enrolled signer; the profile URL is labelled assumed |
| F9 | Out of scope (D07 excludes PDF) |

## Waiting on Ronok

1. Does the harness-hosted live run count toward D07's "one real evidence source", or must it wait for the release gate? Until he answers it is recorded as "intake verified, release gate pending".
2. Should evaluators that rely on current state (still unpaid, not refunded, still active) require a maximum observation age, and how long? No cutoff was added.

Both have no recommended default and were put to him by the overview session.

## Remaining gaps

- **Launch path:** the ordinary launcher accepts deliveries only after the release gate verifies; it is unsatisfied.
- **Margin residual:** a short wrong-month record within 14 hours of the boundary is still admitted, and the evaluator then decides.
- **No refusal audit and no supersede path** (F7a, F7b).
- **Engine conformance not verified here:** whether each financial engine returns *unsupported* for taxes, other currencies, partial periods, ambiguous amendments and business calendars belongs to W2/W3.
- **Coverage gap:** the public feed is truncated to recent incidents; older months refuse as "not in this snapshot".

## External proof still missing

- No release-gated launch of the real source.
- No vendor-signed evidence: the status signer is the local operator who fetched Twilio's page.
- No real customer impact, telemetry or billing source is enrolled, and no real customer agreement exists.
- No real dispute delivery channel (D08 pending).
- No hosted deployment (D11: local only).

## Rollback

Revert on `work/integration-90` in reverse order. No stored row, signature, hash or idempotency key migrates.

- Decision 91: the W4 desk now imports `uptime.evidence_applicability`. Revert W4's F1/F2 follow-up first, or keep the module and remove only the call in `source_config.event_in_scope` and `deliver_evidence.deliver`.
- Decision 91a: delete `evidence_status_source.py`, the two scripts and the test file, then revoke the enrolled grant with `provision_sources.py revoke`. Stored deliveries remain as history.
- Custody audit: delete `evidence_custody.py`, its script and its test. It is read-only, so nothing to undo in data.
- Docs: revert the docs commits; earlier receipts stay in Git history.
