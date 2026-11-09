# Integration 90: file ownership and interface-change requests

**Status:** published November 9, 2026 by the integration owner (session `agent0`, branch `work/integration-90`). This map assigns implementation ownership for concurrent work. It decides no pending team decision. **Update:** later on November 9, Ronok chose D03-A and D04-C. For that implementation only, the identity/scope symbols listed below transfer to `agent1` (`work/identity-pricing-89`) until the commit is handed back for review. D10 (model data policy) and D12 (contextual guide) remain open. See [D03/D04 alternatives](D03-D04-ALTERNATIVES.md).

## Rules

1. One owner per shared schema and central route file. Only that owner edits it. Everyone else sends an **interface-change request** (below) instead of editing.
2. Specialists edit only modules in their own workstream. A change that needs another workstream's module is a request to that owner, not a cross-edit.
3. Shared status records (README, `docs/v4/STATUS.md`, `docs/v4/CAPABILITIES.md`, `docs/ENGINEERING-MAP.md`, `progress/data.json`, `docs/v4/TEST-CHANGES.md` index, `docs/v4/decisions/INDEX.md`) are integrated by W0. Specialists record results in their own workstream ledger (`docs/v4/TEST-CHANGES-<branch>.md`, a receipt under `docs/v4/evidence/<branch>/`) and W0 links them.
4. Pinned evidence is never overwritten. A new run gets a new receipt.
5. A pending team decision blocks only the change that depends on it. Independent work continues. Name the decision ID in the commit when a change stops at that boundary.

## Shared schemas and central routes — single owner: W0 integration

| File | What it defines | Why it is shared |
|:---|:---|:---|
| `uptime/contracts.py` | `Source`, `Outcome`, `Money`, `Citation`, `EvidenceFact`, `EvaluationResult`, `Principal`, `fingerprint` | Imported by about 120 modules and tests |
| `uptime/correspondence_types.py` | Claim `Scope` (account, vendor, contract, service, component, invoice, incident, currency, month, region), the `Id`/`Name`/`Amount` domains and evidence record types | The D03/D04 boundary; consumed by disputes, onboarding joins and interpretation |
| `uptime/claim_identity.py` | Transactional economic identity and dispatch reservation for both claim intake routes | Idempotency and original-filing lineage |
| `uptime/storage.py` | SQLite database opening and table creation | Every persisted workflow |
| `uptime/auth.py`, `uptime/auth_keys.py`, `uptime/auth_client.py` | Reviewer sign-in, P-256 proof of possession, request binding, sessions | Action authorization for every write route |
| `uptime/mandates.py`, `uptime/gates.py`, `uptime/policy.py`, `uptime/local_review_exception.py` | Issuer mandates, release gate, policy modes, the expired CalyxQuay exception | Authority boundaries; changes need explicit team authorization |
| `uptime/server.py` | App factory and 14 route registrations | Central route file |
| `uptime/v4_routes.py` | Mounts the vendor and correspondence routers; resolves terms against inbox evidence | Central route file |
| `uptime/allocations.py`, `uptime/reconciliation.py` | Award/credit/bill allocation and stage ledger | Financial stages shared by disputes and Ramp |

## Workstream modules — owner edits, others request

| Owner | Modules and tests |
|:---|:---|
| **W1 Ramp and financial records** | `uptime/ramp*.py` (except `ramp_webhooks.py` app factory, which is W0), `uptime/credit_steps.py`, `tests/test_ramp*`, `tests/test_reconciliation*`, `scripts/ramp*`, `scripts/verify_ramp_comment.py` |
| **W2 Contract terms and deterministic rules** | `uptime/pricing*.py`, `uptime/governing_fees.py`, `uptime/twilio*.py`, `uptime/other_obligations.py`, `fixtures/northwind/`, matching tests |
| **W3 Vendor onboarding** | `uptime/vendor_*.py`, `uptime/onboarding*.py`, `uptime/public_proposal_*.py`, `uptime/vendor_api.py` (router; W0 owns where it is mounted), matching tests |
| **W4 Disputes** | `uptime/correspondence*.py` except `correspondence_types.py`, `uptime/disputes*.py`, `uptime/correspondence_api.py` (router), matching tests |
| **W5 Evidence and source custody** | `uptime/evidence*.py`, `uptime/source_config.py`, matching tests |
| **W7 Companion interface and guide** | `web/`, `uptime/workbench.py`, `uptime/intelligence.py` (guide answers) |
| **W9 Operations (`gen6`)** | `uptime/installation_revocation.py`, `uptime/workspace_recovery.py`, `uptime/operations_health.py`, `scripts/workspace_recovery.py`, `scripts/operations_check.py`, `scripts/revoke_installation.py`, `tests/test_operations_recovery_90.py`, `docs/v4/OPERATIONS-RECOVERY-90.md`, `docs/v4/CUSTOMER-INSTALLATION-DESIGN.md` |
| **W8 QA, operations and demo** | `uptime/northwind_workflow.py`, `scripts/rehearse.py`, `scripts/setup_*.py`, `scripts/serve*.py`, `scripts/check_repo.py`, browser and journey tests, `docs/v4/OPERATIONS.md`, `docs/v4/DEMO.md` |

`uptime/northwind_workflow.py` registers two routes; it stays with W8 because it only composes existing signed services for the authored walkthrough.

## Session assignments on November 9

| Workstream | Session | Branch |
|:---|:---|:---|
| W0 integration, W8 rehearsal | `agent0` | `work/integration-90` |
| W1 Ramp | `agent4` | `work/ramp-case-lineage` |
| W2 terms/rules, D03/D04 implementation | `agent1` | `work/identity-pricing-89` |
| W3 onboarding | `agent2` | `work/onboarding-generalization-89` |
| W4 disputes | `agent3` | `work/dispute-disposition-89` |
| W5 evidence | `gen5` | `work/evidence-custody-90` |
| W7 interface and guide | `gent7` | `work/finance-guide-90` |
| W9 operations | `gen6` | `work/operations-90` |
| Verification and unseen evaluation (evaluation runners stay unmerged until resumed) | `gent8` | `work/release-evaluation-gent8` |

Transferred for the D03/D04 implementation (`agent1`): `Scope` and the identity types in `correspondence_types.py`, `claim_identity.py`, `allocations.canonical`, the scope/identity join in `v4_routes.py`, identity fields in `ramp_terms_store.py`, overlay identity validation in `vendor_terms.py`/`governing_fees.py` (coordinated with W3), and the shape selection at `correspondence.py:193` (coordinated with W4).

ADR numbers in use: 0089 W4 disputes, 0090 W3 onboarding, 0091 W5 evidence, 0092 verification, 0093 W1 Ramp lineage, 0094 D03/D04 packet, 0095 W7 guide, 0096 W9 operations.

## Interface-change request

Send to the W0 owner (message `agent0`, or open a pull request against `work/integration-90` that touches only your files plus a request note):

```
Interface change request
Requester / workstream:
File and symbol (e.g. uptime/correspondence_types.py: Scope.account):
Current behavior (with a failing test or receipt path):
Proposed change:
Decision dependency (D03/D04/D10/D12 or none):
Migration effect on stored rows, signatures, hashes and idempotency keys:
Tests that must stay unchanged:
```

W0 answers with accept, reject or "blocked on <decision>". A request that changes identity validation, required scope fields, stored hashes or authority is blocked until the team records D03/D04 (or the relevant decision).

## Concurrency limits on this machine

The data volume has only a few GiB free. A full suite with retained temporary trees has filled it before (November 6) and again on November 9 when several suites ran at once. Run focused tests while developing. Run the full suite only after an integration merge, one at a time, with a unique `--basetemp` and `-o tmp_path_retention_policy=failed`, then delete that base directory.
