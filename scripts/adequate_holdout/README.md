# Frozen adequate-evidence investigation

This is an in-family investigation of a studied fictional public agreement. It is
not a vendor-population generalization result or a virgin-source first pass. All
authority is `SCRIPTED_TEST`; `human_approval=false`. No backend code was changed.

The original ten cases, gold, signatures and completed attempts remain immutable.
Their first preserved result is 126 passed observations, 13 failures and nine
unmeasured stages, with 2/10 complete cases and 0/5 denial expectations. Neither
later attempts nor additive cases replace that result or its denominator.

## Separate cohorts and actual results

Both final attempts used source `8d5a8034a58b3cef2f9974783beb1f5869e44edb`.
Application, extraction, harness and frozen-input hashes were stable before/after.
Transport was **TestClient**, because loopback `bind` returned `EPERM` in this
worker's sandbox. These are actual authenticated routes, with no dependency,
handler, evaluator, provider or database-result replacements.

| Cohort | Cases | Complete | Evaluation expectations | Denial expectations | Passed / failed / unmeasured observations |
| --- | ---: | ---: | ---: | ---: | --- |
| Original frozen cohort | 10 | 2/10 | 2/10 | 0/5 | 126 / 13 / 9 |
| Explicitly new additive cohort | 8 | 1/8 | 8/8 | 0/7 | 122 / 7 / 17 |

See [original attempt 06](report-attempt-06.json),
[additive attempt 02](report-additive-02.json), and
[failure classifications](diagnosis.json). Earlier reports are preserved.
Passing arithmetic does not establish a working filing or dispute workflow.

## What failed and why

Eight original evaluation failures and two original denial failures are caused by
inadequate original test design: the frozen historical proofs contain no required
filing fields. Having the invoice now does not establish what an original filing
contained. The two deliberate missing-scope/missing-invoice controls correctly
remain insufficient. Gold is preserved even where its assumptions are wrong.

Three original ordinary submissions and seven additive workflow checks expose a
backend filing-reference mismatch. The public aggregate profile requires fields
such as `service`, `subscription fee` and `any operator coaching fee`. The signed
wire schema accepts identifier references, including invoice source identifiers.
The resolver instead requires the spaced service display name, which the wire
identifier schema rejects. Its billing vocabulary recognizes plural `fees` but
not singular `fee`; its line-reference set also excludes the separately required
coaching row. The actual API reports that each filing field must identify its
independently supported source record and withholds original submission actions.

Three additive historical originals and their independently selected denials
entered the normal signed event API. Four additive ordinary originals stopped
before denial delivery. Thus correct-denial handling, cures, ambiguity and partial
awards have **not** passed this cohort. The private handoff identifies every
failed/unmeasured observation and its transcript digest. No current failure was
established to require an unsupported contractual operator. Exact decimal equality
is accepted by this backend version; the earlier integer-only limitation is
historical.

The additive eight were frozen separately before their first exercise or backend
implementation investigation. Their selection used the public agreement and wire
schemas, with prior aggregate failures and original authoring structure already
known. They are not blind. They supply complete signed monthly records, original
filing contents, original source/version/order commitments, independent amounts
and new denial texts. Their seven denials cover correct threshold, late filing,
mistaken threshold, missing invoice detail, ambiguity, partial award and exact
threshold equality. The eighth case tests the inclusive filing cutoff.

## Observation and scoring boundary

`run.py` first verifies the local freeze, then archives the exact application
source and extraction inside a fresh private attempt. It imports the archived
application and rejects an import from another checkout. Source and harness hashes
are checked again at the end. Local configuration only enrolls independent source
signers and the reviewer, installs exact packet mandates, and sets the existing
synthetic correspondence clock. There are no real vendor or financial dispatches.

Candidate creation, separate reviewer scenarios, interpretation, approval,
activation, evaluation, case audit, correspondence, rollback and changed-version
refusal all use the normal routes. The original reviewer fixtures also omitted
historical fields. Current runs therefore use a separately frozen, fully specified
additive reviewer suite, with a distinct manifest hash, instead of manufacturing
those fields in the old shadow inputs.

The observer never reads expected outcomes or amounts to choose a request. It
uses actual offered actions and exactly binds each local scripted mandate to the
offered packet. It saves the full observation transcript before decoding gold.
`scoring.py` then compares observed states and actual amounts with frozen expected
values. Hashing gold for integrity before execution is not decoding it. Missing
or interrupted measurements cannot become passes. Additive response checks also
measure the absence of an offered action for correct denials and human review;
they do not count that refusal as an executed response.

The adapter preserves quantities, completeness, timestamps and missing fields.
Permitted transformations are a public-title join, list/map filing representation,
and an exact grammatical fee-category suffix. Duplicate fields cannot be collapsed.
An independently frozen original source/version/order commitment permits binding
the API's `contract_version` and `contract_source_sha256` after public GET and
signature verification. The source digest and claim scope must match. A current
GET alone never supplies historical provenance; old missing pins remain absent.
Wire projections and original signed assertions are retained separately.

The response-submit API actually returns `AWAITING_VENDOR`; the scorer uses that
state and `ledger.disputed_remainder`. It does not infer success from an offered
action, attempted request or partial trajectory.

## Reproduction and privacy

Private fixtures, gold, keys, source copies, signatures, databases, HTTP bodies and
failure indexes stay outside the repository. Public reports contain only hashes,
aggregate counts, version/dependency metadata and limitations. `save` uses
create-only writes; every retry gets a new attempt and report. The runner rejects
a private cohort placed inside this repository.

Use operator-supplied paths; the exact local commands and pinned paths are in the
private `ADEQUATE-HANDOFF.md`. Root should use `socket` to obtain real-loopback
evidence. A socket failure is not silently converted to TestClient.

```sh
"$PYTHON" scripts/adequate_holdout/run.py \
  --app-root "$APP_ROOT" --cohort "$ORIGINAL_COHORT" \
  --shadow-cohort "$ADDITIVE_COHORT" --extractions "$EXTRACTIONS" \
  --transport socket --public-report "$NEW_ORIGINAL_REPORT"

"$PYTHON" scripts/adequate_holdout/run.py \
  --app-root "$APP_ROOT" --cohort "$ADDITIVE_COHORT" \
  --extractions "$EXTRACTIONS" --transport socket \
  --public-report "$NEW_ADDITIVE_REPORT"

uv run --locked pytest scripts/adequate_holdout/test_witness.py
```

The harness tests cover missing/partial observations, duplicate recording,
gold-independent action selection, amount scoring, immutable source commitments,
scope mismatches, freeze tampering and exact API stage names. No full2000 suite is
part of this investigation.

All 25 harness checks pass and are included in normal test discovery through
`tests/test_adequate_holdout.py`. The normal application regression on the pinned
archive recorded 2,031 passed, eight failed, three skipped and 38 setup errors.
The archive lacked Git metadata needed by provenance tests. A targeted rerun in a
real detached Git worktree at the same SHA recorded 180 passed and one failure,
clearing those setup errors and a Hypothesis timing failure. The remaining
non-socket failure is the pre-existing generality-control test expecting
`NEEDS_EVIDENCE` but observing `HUMAN_REVIEW`. Four real-socket tests fail at sandbox
`bind`. The normal regression is therefore not a clean pass; its private logs and
exact rerun commands are retained in the handoff.
