# Independent review: evaluation84 NO-MODEL preflight and evaluate_disputes_86 (public copy, 2026-11-09)

**Scope.** I reviewed only the four files in this directory: `preflight_evaluation84.py`, `evaluate_disputes_86.py`, `claim_scope.py` and `correspondence_types.py`.

**What I did not do:**
- I executed nothing. The tests have not been run.
- I opened no corpus, gold, fixtures or network resources.
- I authored no application fix.

**Unverified items.** Anything marked *(unverified)* depends on code that is not in this copy: the claim route, `v4_routes.resolve_active`, `uptime.source_identity`, `vendor_api`, and `evaluate_onboarding_85`.

## 1. Bugs in `preflight_evaluation84.py` (the "ready" signal can be false)

| # | Location | Bug | Effect |
|---|---|---|---|
| P1 | `dispute_case` L107-127 | Validates only `Claim`. Under D04-C, `component`/`incident`/`region` are optional (`correspondence_types.py` L31-36). Intake also runs the server-selected family check: `claim_scope.resolve` → `variant_for` → `check` (`claim_scope.py` L84-88, L120-136). | A monthly-family claim with no incident is reported as `SCOPE_ACCEPTED`, but the route refuses it with `InvalidClaimScope`. `dispute_scope_blocked` (L171) and `dispute_blocked_by_D04` (L189) undercount. `'route': '/api/correspondence/claims'` (L124) is reported even though no route logic was evaluated. |
| P2 | L31-33, L121, docstring L9 | The D04 bucket means "schema says field missing". After D04-C, an absent field can never produce a schema error, so the bucket can only catch pattern errors. The docstring still calls D04 "pending" (it was decided 2026-11-09). `invoice` is bucketed as a scope requirement, but it is never an obligation field (`claim_scope.py` L8-9, L27). | The D04 counts are stale and structurally near-zero. |
| P3 | L120-122, L126 | Buckets by `loc[-1]`. The null refusal from `Scope._absent_is_not_null` (`correspondence_types.py` L38-43) has `loc=('scope',)`, so it lands in `other`. Nested identity-type errors whose loc ends in a non-field element would also be misbucketed *(unverified: depends on SourceIdentity)*. An int loc element makes the sort key at L126 compare int with str, which raises `TypeError`. | D03/D04 attribution is wrong, and the whole run can crash. |
| P4 | `_derived_scope` L99-104, L112, vs runner `plan_cases` L420-426 and `intake_claim` L440-447 | The preflight drops `None` values (a source null becomes absent). The runner forwards them as-is, and raises `KeyError` when a key is absent. The preflight builds `claim_id` as `'inbox-'+claim_ref`, while the runner takes a caller-supplied `claim_id`. | The preflight validates a different request than the one the runner would POST. |
| P5 | `claim_basis_activation` L130-160 | Never checks the identity predicate the route actually uses: manifest `vendor` and overlay `account`/`agreement`/`product` must equal the claim's `vendor`/`account`/`contract`/`service` (`claim_scope.py` L112-116). Also never records the adapter's `family`. | A contract can "reach SHADOW" even though the claim still resolves to no family. |
| P6 | L191-193 vs its own docstring L133-135 | Counts `SHADOW` or `ACTIVE` as success, but the docstring says claims resolve only through an ACTIVE adapter. Separately, `claim_scope._installed` admits every state except REVOKED/QUARANTINED (L111). That is two different install-state predicates *(resolve_active unverified)*. | Readiness is over-reported. Admission and term resolution can disagree. |
| P7 | L144-147 | Activation reads `fixtures/.../onboarding/<parent-dir-name>/{document,customer}.json`. That path is derived from `claim_basis.document_path` and the bytes are not checked against manifest pins. Two bases with the same parent directory name would collide. | The source-frozen preflight reads unpinned bytes. |
| P8 | Docstring L4 vs L152, L173; constants L177 | The docstring says no application server or database is used, but `build()` always runs `create_app` with a TestClient on a temp DB. `model_calls: 0`, `gold_opened: False` and `network: False` are constants, not observations. | The receipt asserts things that were never measured. |
| P9 | L94-95 | `fee_authority_reachable_on_draft_path = False` is hard-coded, justified only by a comment about `vendor_api` *(unverified)*. | Fee authority looks checked, but it isn't. |
| P10 | L74, L110, L164 | The manifest is re-read for each onboarding entry. Its digest is recorded but never compared with the runner's pin (`evaluate_disputes_86.py` L380). `dispute_case` parses source bytes without a pin check, and `_pins` hashes a different read. | TOCTOU: the preflight can validate a different corpus than the one the runner pins. |
| P11 | L77-83, L170 | Only `ValueError`/`OSError` are classified. A `KeyError` from `pins[...]`, or `git rev-parse` with `check=True` outside git, aborts the whole run instead of producing a per-case setup failure. | One setup gap hides all the other results. |
| P12 | Whole module | A single outcome, `SCOPE_ACCEPTED/REFUSED`, has no stage. Setup, schema, route, adapter and fee-authority failures can't be told apart. | This doesn't meet the required failure reporting. |
| P13 | L24-25, L204 | `sys.path` is mutated at import time. The receipt is written 0644 with no fsync, while the runner writes 0600 with atomic links. | Minor. |

## 2. Attempt consumption and classification in `evaluate_disputes_86.py` (reported only; not changed)

1. **Marker before lock.** In `SpooledPublicClaude.__call__`, L240 writes the once-only `call.marker` before L241 tries `_ACTIVE`. A concurrency refusal then raises with the marker already written and no `call-result.json`. The result: a technical refusal consumes the first attempt and leaves no terminal record.
2. **Marker before an unguarded parse.** `dispatch_model_job` writes `dispatch.marker` (L302) and then POSTs. `_json` (L265-266) calls `.json()` without a guard. A non-JSON error body or a transport exception leaves the marker and no `dispatch.json`. `denial_views` has the same pattern (L485-487).
3. **Server-side consumption without a local record.** `intake_claim` (L448-454) records nothing if the response isn't JSON, but the server may already have created the claim. A retry would then hit a duplicate, so the attempt is consumed silently.
4. **Status collapsed to one bit.** `intake_claim` L453 maps anything other than 200 to `SETUP_REFUSAL`. That merges schema 422s, `InvalidClaimScope`, 401/403 authorization failures and 5xx errors.
5. **Obligation fields never read.** `not_stated` (L386, L431) is vacuous: `stated` only ever holds the six `SOURCE_SCOPE` keys, so all four obligation fields are always listed. The runner never reads `component`/`incident`/`region`, even when a source states them, so every monthly-family case is guaranteed a route refusal. Each obligation field needs a literal source path that is preregistered, with absent staying absent.
6. **Misleading name.** `claim_basis_family` (L432) holds an onboarding entry id. It is not the obligation `family` that `variant_for` keys on.
7. **Process-wide monkeypatch.** The patch of `transport.bounded_run` (L243-248) applies to the whole process. `_ACTIVE` serializes only this wrapper, so other threads that use the transport (for example a job pool) would spool into this case's folder.
8. **Caller-chosen case list.** `assert_all_terminal`/`read_gold` (L136-142, L357-370) trust the `case_ids` the caller passes. Passing a subset unlocks gold early. Bind this to the digest of the frozen plan's case list.
9. **Incomplete source pin.** `pin_current_code` (L89-101) pins `uptime/`, `web/` and the runner, but not `scripts/` (the preflight, `evaluate_onboarding_85`, `public_proposals`). `.split()` (L93) also breaks on paths containing whitespace.

## 3. `claim_scope.py` observations (application code; no fix authored)

- **Setup gaps look like family refusals.** A missing table returns `[]` (L104-105), which produces the "unknown family" refusal. A missing install therefore looks the same as an unknown family. The preflight has to check setup separately.
- **Null `label_bindings` crashes.** `label_bindings: null` raises `AttributeError` at L77, which is a server error, not `InvalidClaimScope`. A null `resource_label` adds the word `none` to the resource vocabulary (L81).
- **Exact-token vocabulary matching.** `Incidents`, `outages` and `TicketNumber` don't match `INCIDENT_WORDS`, so a family may skip a requirement the filing actually needs. This is a policy question, not a change request.
- **Built-in profile asymmetry.** `builtin_twilio` casefolds the vendor but compares the service exactly (L72). A matching Twilio adapter alongside the built-in profile is refused as ambiguous (L129-130). Confirm both are intended.
- **Install filter is wide.** The filter at L111 admits any state other than REVOKED/QUARANTINED. Confirm that state vocabulary.
- **Monthly still requires incident (L87-88).** I kept this behavior, and a test guards it.

## 4. New files (not executed)

- **`preflight_scope_finish.py`** provides `check_schema_and_family(claim_payload, manifest, overlay)`.
  - **Pure and write-free.** It uses the real `Claim` model and the real `claim_scope.resolve` / `variant_for` / `check`. `resolve` runs on a private in-memory SQLite holding at most one adapter row, so the real identity SQL, built-in profile and ambiguity rule apply.
  - **Classification.** Results fall into setup / schema / adapter / route / preflight-disagreement stages:
    - `SCHEMA_INVALID`
    - `SCOPE_UNRESOLVABLE` (`NO_GOVERNING_TERMS` / `UNSUPPORTED_FAMILY` / `AMBIGUOUS_FAMILY`)
    - `FAMILY_SCOPE_MISSING`
    - `FAMILY_SCOPE_NOT_APPLICABLE`
    - `SCHEMA_AND_FAMILY_ADMISSIBLE`
  - **Exact values.** It copies the source exactly and reports explicit nulls. It flags any value the schema changed. If the schema adds or drops an obligation field, it returns a disagreement rather than admitting.
  - **No readiness claim.** It lists `not_checked`, including install state, the server manifest, fee authority, D03 policy and evidence, and it never emits `READY`.
- **`test_preflight_scope_finish.py`** contains 26 test functions using only data authored in the file. They cover:
  - each outcome class
  - parity with the real `variant_for`/`check`
  - the monthly-incident guard
  - exact identity matching (case and whitespace)
  - explicit null vs absent
  - strict no-coercion
  - input non-mutation
  - determinism

## 5. Integration recommendations (for the parent)

1. **One request.** Build the claim request once, from literal source paths only, and feed the same object to both this function and the runner. Never derive or fill a field.
2. **Server manifest only.** Pass the **server-installed artifact** manifest and overlay, for example as captured from the deterministic candidate/install response *(unverified that it is exposed)*. Never pass corpus `document.json`: that will produce false `UNSUPPORTED_FAMILY`.
3. **Per-case stage record.** Write one record per case with `setup`, `schema`, `route`, `adapter` and `fee_authority`, each `PASS`/`FAIL:<class>`/`NOT_CHECKED`. Fee authority should be `NOT_CHECKED` until it is actually observed. Catch per-case exceptions so that one gap doesn't abort the run.
4. **Write-free preflight.** Refuse to start if the preflight is pointed at an attempt root or an evaluation DB.
5. **Parity test.** Add a test that runs the same authored cases through the real route on a migrated DB with a real install, and asserts the HTTP refusal class matches this function's class. Until then, treat this function as a model of the route, not as the route itself.
6. **Pin the preflight.** Pin `scripts/`, including this file, in the source freeze.

## 6. Preregistered after-remediation evaluation (outline only; nothing run, no results)

1. **Freeze before running.** Freeze the following, and publish their digests before the first case runs:
   - source commit and a tree digest over `uptime/`, `web/` and `scripts/`
   - the `claim-scope/1` table and the `Claim` schema digests
   - the case list digest, outcome taxonomy, metrics, denominators, and exclusion and stop rules

   Any drift voids the run and requires re-registration.
2. **New cases with fixed provenance.** Cases must be new and written after remediation by named authors. Each case gets an immutable provenance label at authoring: `HUMAN_INDEPENDENT`, `HUMAN_TEAM`, `MODEL_ASSISTED`, `MODEL_AUTHORED` or `SCRIPTED`.
   - Independent authors have no access to the fixes, their tests, the frozen corpus gold or system outputs.
   - Model-authored or model-assisted cases and controls are reported in their own tables. They are never pooled with or described as independent human evidence.
   - A custodian seals gold, hashed, before any run. Gold is never derived from system output.
3. **Strata, with counts preregistered:**
   - family: monthly (incident), resource (±region, filing-word driven), service-month, built-in
   - onboarding vs dispute
   - positive cases vs semantic negative controls

   Whole-month claims are a preregistered **policy-blocked** stratum. Their expected result under the current policy is a refusal.
4. **One attempt, no retries.** The write-free preflight runs first. A case that fails it stays in the denominator as not-reached at that stage.
5. **One outcome per case.** Outcomes are mutually exclusive and assigned at the first failing stage: SETUP, SCHEMA, ROUTE_SCOPE, ADAPTER, FEE_AUTHORITY, TECHNICAL_REFUSAL (timeout, output limit, transport, concurrency, non-JSON) or COMPLETED. Only COMPLETED cases are scored against gold.
6. **Separate metrics, never pooled:**
   - **Meaningful success:** a positive case reaches COMPLETED with the gold terminal stage and exact decision/amount, no invented scope field, and no unauthorized action. The denominator is all registered positive cases. Also report the rate conditional on reaching COMPLETED. A system that refuses everything must score 0.
   - **Semantic negative controls:** the correct result is a refusal for the stated class. Examples:
     - monthly claim without an incident → `FAMILY_SCOPE_MISSING`, not INSUFFICIENT_EVIDENCE
     - identity mismatch → `NO_GOVERNING_TERMS`
     - a field that is not applicable
     - an unsupported family
     - a whole-month claim

     The control passes only if the refusal class is right.
   - **Technical refusals:** counted and listed by cause. They never count as a success or as a correct negative, including on negative controls.
   - **Authority:** kept in a separate ledger:
     - acting principal (`SCRIPTED_NOT_ACTUAL_HUMAN` vs a real person)
     - authorization-stage failures, kept separate from judgment misses
     - whether fee authority was reached
     - zero financial or external actions

     Scripted approvals are never reported as human approvals.
7. **Gold unlocks only after every registered case id is terminal,** checked against the registered digest.
8. **Reporting.** For each stratum, report n and the denominator, exact (Clopper-Pearson) intervals, and a per-case listing. Keep a deviation log. Make no coverage or readiness claim beyond the observed strata. Compare with the frozen corpus only through its own separately registered run.

## 7. Risks of the new files

- **Not run.** If a test fails because of SourceIdentity constraints on the authored values, the baseline test points to that. If SourceIdentity changes case or whitespace, the exactness tests fail. That would be a real finding about "exact source values", not a test bug.
- **Assumed route.** I assume the route does `Claim.model_validate(body)` and then `claim_scope.admit(db, tenant, claim.scope)`. The route source isn't here. It may also validate JSON bytes (JSON mode) rather than Python objects; for these string-only fields that should not matter, but a parity test is needed.
- **Private helper and assumed state.** The module uses the private `claim_scope._installed` on a two-table projection containing only the columns that its SQL names, with the state assumed `ACTIVE` (this is reported in every record). If that query or the state vocabulary changes, results drift. Pin the `claim_scope.py` digest.
- **Error strings.** Schema error `type` strings (`missing`, `extra_forbidden`) are Pydantic v2 vocabulary.
- **Guard test.** The monthly-incident test is meant to fail when the whole-month policy lands. Update it deliberately at that point; don't delete it.
