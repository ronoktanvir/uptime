# Integration 90 — completion checklist and handoff

Integration owner: session `agent0`, branch `work/integration-90`, baseline `03b372e` (hosted CI: 3,967 passed, 1 warning in 417.83 s; 75 JavaScript checks).

| Record | Purpose |
|:---|:---|
| [REQUIREMENTS.md](REQUIREMENTS.md) ([JSON source](requirements.json)) | Every original V3 requirement with disposition, evidence, gap class and owner (189 items) |
| [OWNERSHIP.md](OWNERSHIP.md) | One owner per shared schema and central route; sessions and branches; interface-change requests |
| [INTERFACES.md](INTERFACES.md) | Published identity, scope, evidence, financial-stage and authorization interfaces |
| [D03-D04-ALTERNATIVES.md](D03-D04-ALTERNATIVES.md) | Alternatives, migration consequences, one Opus critique; Ronok's November 9 choice: D03-A with a blocking guard, D04-C |
| [BLOCKERS.md](BLOCKERS.md) | Unresolved blockers by type, owner and unblocking decision |
| [REHEARSAL.md](REHEARSAL.md) | Final two-minute script, pre-filming checks, Q&A, fallbacks, presentation listener and rehearsal record |
| [D06-ACTION-MATRIX.md](D06-ACTION-MATRIX.md) | Every action with its D06 target: person, policy-eligible or never |
| [AGENTS-D14-PROPOSAL.md](AGENTS-D14-PROPOSAL.md) | Proposed `AGENTS.md` change for D14; awaiting Ronok's confirmation |
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

## Rounds 2 and 3 (after `7b6be51`)

| Commit | Kind | What |
|:---|:---|:---|
| `1f6238e`, `a8bc96e`, `3dbe8ab` | merge, fix | D03-A identity (agent1), Ramp association on `source-identity/1` (agent4), reconciliation identity check (W0) |
| `0f39570`, `a3bfefc`, `cc35de4`, `ec3c9fe`, `16c4635` | merge | W7 finance view, grounded read-only guide, abstention, denial UI, route sweep |
| `39ee3f0`, `1f2b8b4`, `ada6c78` | merge | W4 89b intake scope, 89c wire identity, 89d narrow F3 (delegated) |
| `6a5136c`, `0a7fa5e` | merge | W5 Twilio public status source (decision 91a), custody audit |
| `b36827f` | feat | Ronok's 2a: closure-bound accept-denial mandate |
| `c69d2ca` | fix | Webhook hardening (W1 request) |
| `8912307`, `b85e309`, `296ee1b` | merge | W9 preflight and demo-machine runbook; W1 outbox fixes and pre-filming check; W3 D05 phase 1 |
| `14805a5`, `51f1148` | test | Verification-lane probes (D03 invariant, socket authority, tenant crossing, source change, injected reply) |
| `636b6e8` | test | **Round 3 on `fde492c` (demo build): 4,523 passed, 1 warning** |
| `12756a1` | test | Demo build over real HTTP; presentation listener on 8776 |
| `c3b7e0f`, `fb7495b`, `7f41a0d`, `4d9bf63`, `4f918a1`, `1a36ecd` | merge | After the demo build, covered by round 4: D09 read-back, W5 acceptance controls, D03 name extension and F5, W4 89e/89f, ADR-0089 addenda |

Decision records: Ronok's own decisions are D03 (including the name extension), D04-C ("monthly keeps incident"), D05, D06, D07, D10, D11, D12, D13, D14, the guard with no override, F5, and 1a/2a/3a. Delegated (handoff defaults chosen by the overview session): D01, D02, D09, F3 option A and the familiar-denial closure. D08 is with Ronok. See [the handoff](../TEAM-DECISION-HANDOFF.md#team-decision-sheet) and [D06 action matrix](D06-ACTION-MATRIX.md).

## Rollback

Nothing has been merged to `main` or `v4/integration`; `origin/main` is still `03b372e`.

- To drop one specialist increment, revert its merge commit on this branch, for example `git revert -m 1 572d5b5`. Then rerun `uv run --locked pytest` and record the result. Each increment touches only its own files, plus index lines in `TEST-CHANGES.md`, `decisions/INDEX.md` and `CAPABILITIES.md`.
- To drop the W9 mandate gate alone, revert `682d071` inside the W9 history. Native preparation remains gated by its other check (ADR-0096).
- The CalyxQuay corrections are documentation. Reverting `8da2a3f` restores the stale wording, but the receipt it removes is the only reproducible record of the review, so keep the receipt.
- The checklist test (`0448783`) can be reverted independently. Removing an ID instead is a visible test change for the ledger.
- No database, credential, Ramp object, review grant or worktree belonging to another session was modified or deleted.

## External proof still missing

An Uptime-origin Ramp write and read-back; a real vendor credit, award or bill application; a governing agreement for a connected Ramp bill; a real claim delivery channel; general release-gate evidence (independent unseen-vendor and unseen-dispute results with a human witness); a timed human rehearsal and a Northwind film. Details: [BLOCKERS.md](BLOCKERS.md).
