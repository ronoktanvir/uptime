# Integration 90 — completion checklist and handoff

Integration owner: session `agent0`, branch `work/integration-90`, baseline `03b372e` (hosted CI: 3,967 passed, 1 warning in 417.83 s; 75 JavaScript checks).

| Record | Purpose |
|:---|:---|
| [REQUIREMENTS.md](REQUIREMENTS.md) ([JSON source](requirements.json)) | Every original V3 requirement with disposition, evidence, gap class and owner (189 items) |
| [OWNERSHIP.md](OWNERSHIP.md) | One owner per shared schema and central route; sessions and branches; interface-change requests |
| [INTERFACES.md](INTERFACES.md) | Published identity, scope, evidence, financial-stage and authorization interfaces |
| [D03-D04-ALTERNATIVES.md](D03-D04-ALTERNATIVES.md) | Alternatives, migration consequences, one Opus critique; Ronok's November 9 choice: D03-A with a blocking guard, D04-C |
| [BLOCKERS.md](BLOCKERS.md) | Unresolved blockers by type, owner and unblocking decision |
| [REHEARSAL.md](REHEARSAL.md) | Final two-minute script, disclosures and rehearsal record |
| [SETUP.md](SETUP.md) | Fresh-checkout reproduction |
| [../TEST-CHANGES-90.md](../TEST-CHANGES-90.md) | Test changes on this branch |

Corrected current-status records (history preserved): [LOCAL-REVIEW-EXCEPTION.md](../LOCAL-REVIEW-EXCEPTION.md), [DEMO-PATH-87.md](../DEMO-PATH-87.md), [STATUS.md](../STATUS.md), [TEAM-DECISION-HANDOFF.md](../TEAM-DECISION-HANDOFF.md), [CAPABILITIES.md](../CAPABILITIES.md), [ENGINEERING-MAP.md](../../ENGINEERING-MAP.md). Recorded review receipt: [recorded-review-20261109.json](../evidence/local-review-88/recorded-review-20261109.json).

## Commits on `work/integration-90` (from `03b372e`)

| Commit | Kind | What |
|:---|:---|:---|
| `2205f0a` | fix | Browser sign-in sends the login path and empty body hash; picker accepts `.jwk` (from the `$HOME/uptime` working tree) |
| `37d73f2` | test | Hard-kill restart probe for the served Northwind flow (from the verification lane, `52bea97`) |
| `8da2a3f` | docs | Recorded CalyxQuay review (REVOKED at revision 9) and the human-posted Ramp note; read-only receipt |
| `513d465` | docs | Ownership, interfaces, D03/D04 alternatives with one Opus critique, blockers, rehearsal, setup |
| `0448783` | test | V3 requirement checklist (189 items) and its traceability test |
| `f07f61a`, `e200201` | merge | W3 requirement card and refusal diagnostics (`f9153b2`, `edf0c05`) |
| `8147f78`, `c5c50a0` | merge | W5 evidence period applicability (`5b02d61`, `dcec513`) |
| `572d5b5` | merge | W1 Ramp case lineage (`1c8bc86`) |
| `8ed847e` | merge | W9 operations recovery, installation revocation, mandate gate (`27e4926`) |
| `e6e8b6b` | docs | D03/D04 decision record (owner Ronok, 2026-11-09) and agreed interfaces |
| `2beb1d3` | docs | November 3 orchestration records marked as historical |
| `64343fa` | test | Fresh-clone suite at `1b627ad`: 4,110 passed, 1 warning; status and progress refreshed |
| `b5cd49e` | merge | W4 reviewed denial acceptance and dispute trace (`16116ee`). Covered by hosted CI at `64343fa` (4,147 passed, 1 warning) |
| `0f39570` | merge | W7 finance view, grounded read-only guide and refusal-diagnostic UI (`db779c3`). **Not yet covered by a full suite** |
| `93d896a` | docs | Ronok's D05, D06, D07 and D11 decisions and the D04 clarification |

Other commits link ledgers, ADRs and capability rows.

## Rollback

Nothing has been merged to `main` or `v4/integration`; `origin/main` is still `03b372e`.

- To drop one specialist increment, revert its merge commit on this branch, for example `git revert -m 1 572d5b5`. Then rerun `uv run --locked pytest` and record the result. Each increment touches only its own files, plus index lines in `TEST-CHANGES.md`, `decisions/INDEX.md` and `CAPABILITIES.md`.
- To drop the W9 mandate gate alone, revert `682d071` inside the W9 history. Native preparation remains gated by its other check (ADR-0096).
- The CalyxQuay corrections are documentation. Reverting `8da2a3f` restores the stale wording, but the receipt it removes is the only reproducible record of the review, so keep the receipt.
- The checklist test (`0448783`) can be reverted independently. Removing an ID instead is a visible test change for the ledger.
- No database, credential, Ramp object, review grant or worktree belonging to another session was modified or deleted.

## External proof still missing

An Uptime-origin Ramp write and read-back; a real vendor credit, award or bill application; a governing agreement for a connected Ramp bill; a real claim delivery channel; general release-gate evidence (independent unseen-vendor and unseen-dispute results with a human witness); a timed human rehearsal and a Northwind film. Details: [BLOCKERS.md](BLOCKERS.md).
