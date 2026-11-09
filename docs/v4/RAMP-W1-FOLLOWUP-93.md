# Ramp (W1) follow-up: pre-filming check, outbox safety and old branches

November 9, 2026. Branch `work/ramp-w1-followup-93`, based on `work/integration-90` at `a3bfefc`, which already includes D03-A and the decision 93 identity switch (`a8bc96e`). Nothing here writes to Ramp, and the native-posting retest stays blocked.

[Test ledger](TEST-CHANGES-ramp-w1-followup-93.md) · [First real pre-filming run](evidence/ramp-lineage-93/prefilm-20261109T123606Z.json)

## Pre-filming check for the demo's Ramp segment

`scripts/ramp_prefilm_check.py` re-verifies, right before recording, what the demo says about the real Ramp bill at 0:28–0:43 of the rehearsal. Ronok or the operator runs it by hand, using the same protected sandbox profile as `scripts/ramp_sync.py`. It is not part of `rehearse.py` or CI, and it refuses to start when `CI` is set.

```bash
RAMP_ENV=sandbox UPTIME_RAMP_CREDENTIAL_FILE=~/.config/uptime/ramp-demo-native.json python scripts/ramp_prefilm_check.py --output-dir ~/.local/share/uptime-engineering/runtime/ramp-lineage-20261109
```

It makes only reads: the business, the observed bill, one bounded records sync (Ramp's agreement list query is a read-only POST), and the offline case lineage built with the committed human-note receipt. It then prints one line and writes one receipt with mode 0600. The output directory must already exist, belong to the operator, have mode 0700 and sit outside the repository; otherwise nothing is read and no credentials are loaded.

| Outcome | Conditions |
|---|---|
| `PASS` | Same business and bill as the [November 9 evidence](evidence/ramp-lineage-93/live-read-20261109.json); same vendor, entity and amount; no credit applied to the bill or created from it; the person-posted note re-observed in this capture; lineage `FINDING_SURFACED` with no refusals or review flags; all case money null. |
| `FAIL` (exit 1) | Any of those differs, or the bill, comment or credit read is incomplete. |
| Warnings (still `PASS`) | The bill's payment or approval status changed, or new comments appeared on the bill. Look before filming; the narration doesn't depend on them. |
| `ERROR` (exit 2) | Local refusal (CI, unsafe output directory) or a provider failure. No receipt is written. |

First real run, 12:36 UTC: `PREFILM PASS bill=f74ba12c comments=376563cf capture=8d42567fdf7e failures=none warnings=none writes=0`. Bill USD 840, `OPEN`, approval `PENDING`, no applied credits; credit and agreement lists complete and empty.

## Outbox safety fixes salvaged from `remediate/native_workflow`

The November 4 branch `remediate/native_workflow` (`c61c384`, never pushed) held fixes to the reviewed Ramp outbox in `uptime/ramp_workflow.py` that integration had since diverged from. Its seven extra tests were run unchanged against integration `a3bfefc`. Three failed, which confirmed the gaps:

| Gap on integration | Fix (commit `16ca1a4`) |
|---|---|
| A newer finding on the same bill produced a different logical action, which could be prepared and sent while the first action's delivery was still uncertain, so a second comment could be posted. | Preparing an action is refused while another action of the same kind on the same object is `UNCERTAIN` or `DISPATCHING`. |
| A stored plan edited without updating its review digest still dispatched, because the signature covers only the digest. | Every row read recomputes the plan digest and checks tenant, business and ID, and refuses on a mismatch. |
| A reset procurement trigger wasn't visible on a delivered metadata action. | Action views report `trigger_current` without rewriting delivery history. |
| Custom-form read-back didn't check the returned ID, and non-string finding sources raised a type error. | Exact ID required; sources must be strings. |

The signed-review recheck at dispatch was already present in integration in another form, so it wasn't ported. The branch's webhook hardening (string event type, exact verification-response shape, a `status()` accessor) is in `uptime/ramp_webhooks.py`, which belongs to W0. It's listed below as a request.

### Restored outbox rows (W9 request, acknowledged)

gen6's workspace restore (W9, `uptime/workspace_recovery.py`) will copy the native outbox and fence a restored copy. I acknowledged it with a narrower fence for comments:
- DISPATCHING → UNCERTAIN.
- REVIEWED → PREPARED with the review cleared.
- PREPARED and BLOCKED unchanged.
- Metadata and decision rows that aren't DELIVERED → UNCERTAIN.

Why: executing a comment always reads its exact discussion for the action's dedup marker before posting, so a comment delivered after the backup is recorded rather than reposted. Marking never-sent comments UNCERTAIN would block those objects permanently, because absence never settles an uncertain action. The plan column is left untouched, so the integrity check above stays valid.

## Disposition of the old unmerged branches

None of these is on origin. None was merged or deleted.

| Branch | Content | Disposition |
|---|---|---|
| `remediate/native_workflow` (`c61c384`) | Outbox and webhook hardening, an offline simulation CLI (`scripts/ramp_workflow.py`), a local webhook service script, mock-HTTP contract tests, `RAMP-WORKFLOWS.md` | **Salvaged in part.** The outbox fixes and seven tests are ported (above). The mock-HTTP contract tests (`tests/test_ramp_workflow_http.py`, 14 functions, 25 cases) are added unchanged: they pass against current code and cover exact native paths, pagination, redirects, timeouts and stale scope receipts. The webhook hardening is a W0 request. The offline simulation CLI and the local webhook service script aren't ported: neither affects the demo, and the service script needs W0's app factory. Keep the branch as the record. |
| `remediate/blind` (`c33642b`, `9364cd2`) | Frozen synthetic evaluation fixture with a `private/` answer set | **Keep unmerged and unpushed.** Private evaluation material; owned by the evaluation lane (decision 84–86 holdouts). Contents were not read. |
| `remediate/ind_hold2` (`cebbef5`) | Frozen third-source holdout and its SHA-256 commitment | **Keep unmerged and unpushed.** Same reason. Contents were not read. |
| `feat/native-qualification-59` (`14fe212`, `3ea3a05`) | Single-use sandbox connection qualification command (decision 63) | **Keep unmerged; must not merge.** It is a disabled native qualification path, and the native-posting retest stays blocked. Not run. |

## Requests to other owners

**W0 (agent0): `uptime/ramp_webhooks.py`.** Port from `c61c384`:
- refuse a non-string event `type` with 400 instead of raising a type error;
- accept a verification response only when it is exactly `{"success": true}`;
- add a read-only `status()` accessor.

Tests from that branch's `test_ramp_workflow_webhooks.py` diff cover these. Decision dependency: none.

**W7 (gent7), INV-7, post-demo.** Per agent0, this waits until after filming so the dashboard stays stable. Interface change request:

```
Requester / workstream: agent4 / W1 (requirement INV-7)
File and symbol: uptime/workbench.py: dashboard stage definitions ("exposure", "estimated", "claimed", "awarded", "posted", "applied")
Current behavior: no evidence-ready stage; "awarded" mixes vendor-reported and any verified awards into one KPI. REQUIREMENTS INV-7 is PARTIAL.
Proposed change: add a nonadditive "evidence_ready" snapshot (deterministic ELIGIBLE with complete evidence, not yet filed); split "awarded" into "awarded_vendor_reported" and "awarded_verified", where verified stays unavailable (not zero) until D09 defines a verified award source. Stages are never summed.
Decision dependency: D09 for verified awards; none for evidence-ready.
Migration effect on stored rows, signatures, hashes and idempotency keys: none; the dashboard JSON gains keys and the UI gains labels.
Tests that must stay unchanged: test_all_recorded_partial_awards_are_counted_once, test_only_exact_pending_prepayment_contributes, test_correspondence_credit_requires_scoped_existing_eligible_bill.
Timing: after the demo recording.
```
