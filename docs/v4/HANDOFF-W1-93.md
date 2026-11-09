# W1 Ramp handoff: decision 93 and its follow-up

**Workstream:** W1, Ramp and financial records, owner `agent4`. **Date:** November 9, 2026, America/Los_Angeles.

All W1 code is merged into `work/integration-90` and pushed with it. The last full suite covering it is round 6 on a fresh clone of `3f60647`: **4,664 passed, 1 warning**. Nothing in this workstream wrote to Ramp. The native-posting retest stays blocked and was never retried or rerouted.

**What remains** needs either a decision from Ronok or the team (see [Blocked on a decision](#blocked-on-a-decision)) or external proof that code can't produce (see [External proof still missing](#external-proof-still-missing)).

Details: [Case lineage](RAMP-CASE-LINEAGE.md) · [Follow-up record](RAMP-W1-FOLLOWUP-93.md) · [ADR 93](decisions/ADR-0093-ramp-case-lineage.md) · test ledgers [93](TEST-CHANGES-93.md) and [follow-up](TEST-CHANGES-ramp-w1-followup-93.md) · evidence in [`evidence/ramp-lineage-93/`](evidence/ramp-lineage-93/)

## Commits

| Commit | Branch | What it does | Merged as |
|---|---|---|---|
| `11edb07` | `work/ramp-case-lineage` | Contract applicability by native IDs; one case's identity checked from record to bill application | `572d5b5` |
| `929d717` | same | Ramp capability verification, live-read summary, real demo-bill lineage, Opus critique | `572d5b5` |
| `d38b8e5` | same | Double-binding review kept when the bound credit isn't observed; note receipt time required | `572d5b5` |
| `a87f457` | same | Accepted non-NFC identities. **Superseded by `a8bc96e`**: it followed an incomplete relayed summary of D03 | `572d5b5` |
| `1c8bc86` | same | Shared index lines handed to W0 instead of edited | `572d5b5` |
| `e8cb350` (local) | `work/ramp-identity-d03a-prep`, never pushed | Account and agreement identities delegated to `source-identity/1` | cherry-picked as **`a8bc96e`** |
| `16ca1a4` | `work/ramp-w1-followup-93` | Outbox: no new action on an object with an uncertain delivery; tampered stored plans refused | `b85e309` |
| `78c61e0` | same | 25 mock-HTTP contract tests restored from `c61c384` | `b85e309` |
| `4768bca` | same | Read-only pre-filming check, with its first real run | `b85e309` |
| `d3caec2` | same | Follow-up record, old-branch dispositions, requests to W0 and W7 | `b85e309` |
| `1ae1960` | same | Complete vendor list (411) recorded | `b85e309` |
| `14c672a` | same | D09 both-sided credit/bill read-back | `c3b7e0f` |
| `bbcb528` | same | D02 and D09 recorded in the operator procedure | `c3b7e0f` |
| (this commit) | same | This handoff | to merge |

Requests applied by their owners:
- **W0:** webhook hardening, applied as `c69d2ca`.
- **W0:** the index lines from `evidence/ramp-lineage-93/W0-INDEX-REQUEST.md`.
- **W9:** gen6's restore fence for outbox rows (`aba3307`), checked against my spec.

## Files changed

**New.** No existing module, table or schema was replaced.
- `uptime/ramp_association.py`
- `uptime/ramp_case_lineage.py`
- `scripts/ramp_case_lineage.py`
- `scripts/ramp_prefilm_check.py`
- `scripts/ramp_credit_readback.py`
- `tests/test_ramp_case_lineage.py`
- `tests/test_ramp_prefilm_check.py`
- `tests/test_ramp_credit_readback.py`
- `tests/test_ramp_workflow_http.py`
- `docs/v4/RAMP-CASE-LINEAGE.md`
- `docs/v4/RAMP-W1-FOLLOWUP-93.md`
- `docs/v4/TEST-CHANGES-93.md`
- `docs/v4/TEST-CHANGES-ramp-w1-followup-93.md`
- `docs/v4/HANDOFF-W1-93.md`
- `docs/v4/decisions/ADR-0093-ramp-case-lineage.md`
- `docs/v4/decisions/packets/93-ramp-case-lineage.md`
- `docs/v4/decisions/reviews/93-ramp-case-lineage.json`
- `docs/v4/evidence/ramp-lineage-93/` (7 files)

**Modified, W1-owned:**
- `uptime/ramp_workflow.py`: four checks in prepare, row read and view.
- `tests/test_ramp_workflow.py`: seven functions appended; no existing function changed.

## Behavior implemented

- **Applicability** (`ramp_association.associate`). It classifies every observed bill, transaction, PO, agreement and vendor for one contract, using only reviewed native IDs:
  - `APPLICABLE`, `NOT_APPLICABLE` or `CONFLICT`.
  - `UNKNOWN` means missing evidence, never "doesn't apply".
  - Names, amounts and dates are never matched. Account and agreement identities follow D03-A `source-identity/1` and are refused, never rewritten.
- **One case record** (`ramp_case_lineage.build_lineage`). It checks the same tenant, business, vendor, entity, record, contract and claim through seven stages: record, applicability, finding, surface, award, credit, application.
  - The first mismatch stops the chain.
  - Money stages are kept separate and never summed. `actual_recovery` is always null.
  - Applied value counts only when both sides report it.
  - Each of these needs review: a reduced application, a credit missing from a later read, one credit bound to two cases, an award split across credits, a credit larger than its award, a note missing from a later complete read, or a hold no longer current.
- **Real demo bill** `f74ba12c`. The chain runs from no governing agreement, to an evidence-gap finding, to the person-posted note verified by read-back. There is no award and no credit, and all money is null. Uptime refuses to attach the Northwind terms to this bill.
- **D09 read-back** (`credit_links`, `scripts/ramp_credit_readback.py`). It reports every credit linked to one verified bill and checks each link on both sides, without attributing anything to an award. On the demo bill it gives `NO_APPLIED_CREDITS`.
- **Pre-filming check** (`scripts/ramp_prefilm_check.py`). Ronok or the operator runs it by hand just before recording. It only reads, writes one owner-only receipt outside the repo and prints one line. It's in the rehearsal checklist.
- **Outbox safety** (`ramp_workflow`). It refuses a different action on the same object while an earlier delivery there is uncertain, refuses stored plans whose content no longer matches the review digest, requires an exact custom-form read-back, and reports whether a trigger is still current.
- **Person-operated credit procedure under D09.** Steps and outcome codes are in [RAMP-CASE-LINEAGE.md](RAMP-CASE-LINEAGE.md#person-operated-credit-procedure-d09). The prepare and confirm functions are tested but not exposed; see [Remaining gaps](#remaining-gaps-not-blocked-on-ronok).

## Tests and actual results

| Test file | Cases | Type |
|---|---|---|
| `tests/test_ramp_case_lineage.py` | 59 | New file |
| `tests/test_ramp_workflow.py` | 7 | Added to an existing file |
| `tests/test_ramp_workflow_http.py` | 25 | New file |
| `tests/test_ramp_prefilm_check.py` | 12 | New file |
| `tests/test_ramp_credit_readback.py` | 13 | New file |

Every case uses a read-only test double driven through the real sanitizer and validator. **Existing test changed:** only `test_exact_identity_keeps_spaces_and_refuses_rewrites`, in this workstream's own file. It changed twice for D03; both changes are recorded in [TEST-CHANGES-93](TEST-CHANGES-93.md).

Full suites run by agent0 on fresh clones (`uv run --locked pytest`):

| Round | Commit | Result | Covers |
|---|---|---|---|
| 1 | `1b627ad` | 4,110 passed, 1 warning | lineage `1c8bc86` |
| 2 | `548c347` | 4,354 passed, 1 warning | identity switch `a8bc96e` |
| 3 | `fde492c` | 4,523 passed, 1 warning | follow-up through `1ae1960`; the frozen demo build |
| 4 | `3758164` | **1 failed**, 4,581 passed | D09 read-back. The failure is outside W1: `tests/test_blind_acceptance.py` (late-denial control), a stale W4 expectation. It passes again from round 4b |
| 4b | `5d8af56` | 4,636 passed, 1 warning | |
| 5 | `6f43a91` | 4,663 passed, 1 warning | |
| 6 | `3f60647` | 4,664 passed, 1 warning | everything in this handoff except this docs commit |

Read-only Ramp reads on November 9, all with no write:
- **11:02 UTC:** business and bill association, plus a records sync.
- **12:36 UTC:** pre-filming `PASS`.
- **12:39 UTC:** vendor list complete at 411.
- **D09 read-back:** `NO_APPLIED_CREDITS`.

Raw captures stay private in `~/.local/share/uptime-engineering/runtime/ramp-lineage-20261109/` (mode 0700); only sanitized summaries are committed. One Opus 5.5 critique was run for decision 93 (session `ac3c67f8-8f6a-453d-be5c-dad919bd1189`, before D14). No later model calls were made. Failed first attempts are kept in both test ledgers.

## Decision references

Attribution follows the integration owner's record (`docs/v4/integration90/README.md`, `BLOCKERS.md`).

| Decision | Who made it | Effect on W1 |
|---|---|---|
| D03-A, bounded exact source identity: names included, near-duplicate guard with no override | **Ronok** | Account and agreement IDs here use `source-identity/1` (`a8bc96e`). The guard sits at claim filing, outside W1 |
| D04-C | **Ronok** | No W1 change |
| D06, humans gate judgment | **Ronok** | A person performs every native credit step; no model output affects a gate |
| D07, D10, D11, D14 | **Ronok** | One currency per case; no customer data to models; stays local; no further mandatory Opus calls |
| D02, informational bill discussion on the exact evaluated record | **Delegated**: overview session, handoff default, 04:48 PST | The person-posted note on `f74ba12c` is that surface; no identity invented |
| D09, operator workflow plus Uptime read-back, with award verification kept separate | **Delegated**: overview session, handoff default, 04:48 PST | Read-back implemented. Preparation stays unexposed until a separate award authority exists |
| Decision 93, case lineage design | `agent4`, after one Opus critique | [ADR 93](decisions/ADR-0093-ramp-case-lineage.md) |

## Blocked on a decision

- **D06 sub-question, Ronok's:** may one person both prepare and execute an operator credit application in Ramp? `confirm_operator_application` records `separation_of_duties` but doesn't enforce it. If Ronok requires two people, it's a one-line refusal plus a test.
- **D09 award authority, Ronok or the team:** which role verifies a vendor award and records the `CreditBinding` that ties a Ramp credit to it. Until a role is named, preparation stays unexposed. Letting the operator supply their own award would merge the two authorities D09 keeps apart.

## Remaining gaps (not blocked on Ronok)

- **INV-7:** a separate evidence-ready stage and separate KPIs for vendor-reported and verified awards in `uptime/workbench.py`. The request to W7 is recorded and held until after filming, as agent0 asked.
- **Ledger merge:** merging the lineage with `AllocationLedger` once an award role exists.
- **D02 contract case:** needs an authored agreement for an existing demo vendor (W2) and a reviewed `NativeAssociation`. None exists today.
- **Read limits:** card transactions (more than 1,000) and approvals exceed the existing read bounds. Archived credits aren't requested.
- **Not ported from the old branch:** `remediate/native_workflow`'s offline CLI and webhook service script.
- **BLOCKERS row on old branches:** it can now cite the dispositions in [RAMP-W1-FOLLOWUP-93.md](RAMP-W1-FOLLOWUP-93.md#disposition-of-the-old-unmerged-branches). The two private holdout branches and the native-qualification branch stay unmerged and unpushed.
- **OAUTH-1:** customer OAuth installation is a later milestone under D11.

## External proof still missing

None of these can be produced by code, and none was attempted:
- a real vendor award;
- a Ramp vendor credit created and applied to a bill by a person, confirmed by read-back;
- a Ramp record that carries a contract case under D02;
- any Uptime-origin Ramp write (the native-posting retest is blocked);
- a payment hold or a configured approval intervention;
- proof of who authored the human note (Ramp's `user_id` proves no identity).

## Rollback

There's no data migration: no table, stored row, hash, signature or receipt was changed. Revert newest first on `work/integration-90`:

1. `git revert -m 1 c3b7e0f`: removes the D09 read-back and the D02/D09 documentation.
2. `git revert -m 1 b85e309`: removes the outbox safety checks, contract tests, pre-filming check and vendor record. gen6's restore fence doesn't depend on the outbox guard. Remove the pre-filming step from the rehearsal checklist too.
3. `git revert a8bc96e`: restores the pre-D03 identity adapter. **Not recommended**: it reopens the non-NFC gap.
4. `git revert -m 1 572d5b5`: removes the lineage modules entirely. The human-note receipt is untouched either way.

The webhook fix `c69d2ca` belongs to W0 and reverts on its own. The private runtime receipts can be kept for audit or deleted. Nothing in Ramp needs undoing.
