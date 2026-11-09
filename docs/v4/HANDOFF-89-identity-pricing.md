# Handoff: identity, claim scope and pricing coverage (decision 89, Agent 1)

**Branch:** `work/identity-pricing-89`. Base `03b372e`; tip includes this handoff.

**Integration:**
- D03-A merged at `1f6238e`.
- The D03 name extension and F5 merged after `448fe38`.
- D04-C merged at `6f43a91`. The round-5 full suite passed on a fresh clone; round 6 also passed.

**Status:** complete for the assignment. One item, whole-month monthly evidence, is blocked only on Ronok's decision.

## Commits

| Commit | Change |
| --- | --- |
| `4ad4506` | Characterization of the D03/D04 defects; financial coverage matrix (`financial-coverage/1`); boundary and fixture-name-independence probes |
| `d2886b3` | Full-suite receipt for the characterization (4014 passed) |
| `6ebaffe` | **D03-A**: `source-identity/1` for accounts and agreements; blocking near-duplicate guard; the ledger refuses instead of rewriting |
| `045b878` | D03 extended to vendor and service names |
| `448fe38` | **F5**: reviewed agreement binding for sources that name no agreement |
| `e29fa3a` | **D04-C**: server-side claim scope family table (`claim-scope/1`), "monthly keeps incident" |
| `6c362da` | D04-C test-change ledger |
| `053c4b8` | A resource region is required only for regional terms or a filing-cited region |
| `c3f6bfe` | Blind-acceptance harness without invented placeholders; newly merged tests aligned |
| `d4c7fcd`, `4716a11` | Verification receipts |

## Files changed

- **Source:**
  - new: `uptime/source_identity.py`, `uptime/claim_scope.py`
  - changed: `uptime/correspondence_types.py`, `uptime/claim_identity.py`, `uptime/vendor_terms.py`, `uptime/allocations.py`, `uptime/ramp_terms_store.py`, `uptime/correspondence.py`, `uptime/governing_fees.py`, `uptime/source_config.py` (W5 hunk, approved by gen5)
- **Clients and fixtures:** `web/v4_ui.js`, `fixtures/northwind/loader.py`, `scripts/setup_northwind.py`, `scripts/blind_acceptance.py`; new `scripts/inventory_source_identity.py`
- **Tests:**
  - new: `test_identity_domain_89.py`, `test_financial_coverage_89.py`, `test_source_identity_89.py`, `test_claim_scope_89.py`, `test_agreement_binding_f5.py`, `test_source_config_d04c.py`, helper `governing_binding_89.py`
  - changed: existing tests, each named with its reason in [TEST-CHANGES-89](TEST-CHANGES-89.md) and [TEST-CHANGES-89-disputes](TEST-CHANGES-89-disputes.md)
- **Docs and evidence:** [identity and scope](IDENTITY-SCOPE-CONTRACT-89.md), [financial coverage](FINANCIAL-COVERAGE-89.md), `coverage/financial-coverage-89.json`, `evidence/identity-pricing-89/` (two read-only inventories and the verification receipt)

## Behaviour implemented

- **Identity (D03).** Account, agreement, vendor and service names follow one versioned rule, `source-identity/1`, at onboarding, claim intake, signed evidence records, new filings and the ledger. A value is refused, never trimmed, case-folded or normalized. The legacy restricted identifier is a property-tested subset, so stored bytes, claim keys, hashes and signatures are unchanged.
- **Near-duplicate guard.** A new filing whose account and agreement differ only by case or spacing from an existing filing for the same obligation is refused (HTTP 409). There is no override path.
- **F5.** A resource source that names no agreement binds an overlay only with the reviewed governing-terms attestation tying that exact agreement to the document. Every stored adapter already names its agreement.
- **Scope (D04-C).** The server resolves the family from installed terms:
  - built-in Twilio needs incident and component;
  - generic monthly needs the incident;
  - a resource claim needs the resource, plus region only for a regional subscription, plus fields its filing cites;
  - a whole-service claim needs only filing-cited fields.

  Not-applicable fields must be absent. An unknown or ambiguous family is refused at intake with `InvalidClaimScope` (409), after authorization; it is never reported as missing evidence.
- **Grandfathering.** Stored ten-field claims serialize byte-identically. `FeeEntry.legacy_scopes` keeps their governing fee, and an invented region is still refused.
- **Pricing and fees.** The audit found no path where unsupported or contradictory terms produce a payable amount. The matrix lists the supported semantics and the refusal for each dimension.

## Tests and actual results

| Run | Result |
| --- | --- |
| Characterization full suite (`4ad4506`) | 4014 passed, 1 warning in 879.42s |
| D03-A full suite (`6ebaffe`) | 4089 passed, 1 warning in 326.89s |
| D03 name extension, identity suites | 3529 passed, 1 warning |
| F5 focused tests | 12 passed; wide set 3082 passed, and the 67 fixture-bound tests then passed |
| D04-C focused set (`c3f6bfe`, 141 files) | 4186 passed, 1 warning in 322.21s, 0 failed |
| Blind acceptance | 37 passed |
| Integration round 5, fresh clone of `6f43a91` (agent0) | 4663 passed, 1 warning in 322.05s; JavaScript 101/101; `check_repo` passed |
| Northwind | January ELIGIBLE 2400.00; April 8,600 unchanged; a fresh setup passes the 11 HTTP steps (adapter activated by the scripted setup, not a human review) |

The warning is the existing Starlette TestClient deprecation notice. No monetary or authority assertion changed, and no frozen fixture, oracle or published receipt was rewritten.

## Remaining gaps

1. **Whole-month monthly evidence (blocked on Ronok).** Monthly claims need an incident because the evidence join reconciles coverage to exactly one incident. The 11 corpus-84 `monthly_tier` cases therefore refuse at setup ("requires incident"), and evaluation 86 is on hold. Only the whole-month evidence-sufficiency decision would change this. That decision changes what evidence proves money.
2. **One renewed adapter review.** Pinned files changed (`claim_identity.py`, `vendor_terms.py` and `governing_fees.py`, together with agent2's F4/F6 in the same batch), so active adapters need one renewed review. The integration owner tracks this as an operator item.
3. **Audit review items, not changed.** None of them creates money:
   - contradictory product scope is reported as missing rather than unsupported;
   - missing evidence takes precedence over unsupported terms;
   - a contradicting observation is reported as missing;
   - a premature receipt is ineligible.

   See the [coverage matrix](FINANCIAL-COVERAGE-89.md#audit-result).
4. Earlier blind and evaluation receipts were produced under the old scope rules and are not reinterpreted.

## Decision references

- **Ronok, directly in this session (2026-11-09):**
  - confirmed D03 and D04;
  - chose D04-C over D04-A;
  - chose "monthly keeps incident";
  - extended D03 to vendor and service names;
  - assigned F5 to this branch.
- **Ronok's choices recorded by the integration owner and relayed by the overview session**, consistent with the above: D03-A with the blocking guard; "no override for now"; F5 "require reviewed binding" (integration `de48db5`, `e6e8b6b`).
- **Delegated (Recommended-default) authority:** none used for this work.
- **Implementation choices within the decided scope, agreed with the integration owner:**
  - Twilio requires component;
  - region only for regional terms;
  - the legacy fee alias;
  - the test App as a D04-C client;
  - `SCOPE_FAMILY_REFUSED` in the blind harness;
  - the W5 hunk, approved by gen5;
  - W4 test-input mapping, approved by agent3.
- **Opus:** the single critique for D03/D04 is decision 94 (`claude-opus-5-5`, session `83b1b59b-7fbe-42e5-84fe-f67986752dfc`), run by the integration workstream. D14 makes further critique optional, and no new consultation was run here.

## Rollback

Revert, newest first: `c3f6bfe`, `053c4b8`, `6c362da`, `e29fa3a` (D04-C); then `448fe38` (F5); `045b878`; `6ebaffe` (D03-A). Intake then refuses spaced identities and partial scopes again.

- Claims accepted under the new rules keep their stored bytes and keys. List them and freeze them for review; never delete or re-key them.
- Adapters renewed under these semantics need fresh review again, never reactivation of their older approvals.
- Earlier commits are docs, tests and receipts only.

## External proof still missing

No actual Ramp write, vendor-awarded recovery, applied Ramp credit, real customer agreement, or actual human source or adapter approval is demonstrated by this work. Northwind remains authored data in the local ledger. No model, Ramp, vendor or reviewer action was taken, and no credentials, customer captures or sealed answers were read.
