# Socket attempt 03: narrower parser gaps remain

The additive cohort improves to **5/8 complete cases**, with **141/146 measured
checks passing**. Its five remaining failed checks come from three replies that
still receive parser proposal `unknown`: a late-filing assertion, an invoice-detail
request, and a partial-credit grant. The request also fails both response-action
checks. These are immediate language-coverage failures, not demonstrated
arithmetic or artifact-verifier failures. Safe abstention preserves authority but
does not complete the requested business workflow.

This independent review inspected preserved socket observations and the exact
frozen application source `797c3d0fa1560291cc99d6a08a7b8bacbbb1d344`. It made no
production, harness, gold, input, or scoring changes. Private text, case labels,
values, signatures, and expected-case records are not reproduced here or in the
new public probes. No network, external model, credential, or live-database access
was used. Archived SQLite databases were opened with `mode=ro&immutable=1`.

## Actual results, without changing earlier denominators

These counts describe attempt 03; they do not replace
[attempt 01](INDEPENDENT-SOCKET-DIAGNOSIS.md) or
[attempt 02](INDEPENDENT-SOCKET-DIAGNOSIS-02.md).

| Measurement | Original frozen cohort | Separate additive cohort |
| --- | ---: | ---: |
| Complete cases | 2/10 | 5/8 |
| Evaluation expectations | 2/10 | 8/8 |
| Original-filing observations | 5/5 | 7/7 |
| Denial deliveries | 5/5 | 7/7 |
| Denial dispositions | 1/5 | 4/7 |
| Frozen artifact delivery | 1/1 | 1/1 |
| Response-approval expectations | 0/1 | 6/7 |
| Response-submit expectations | 0/1 | 6/7 |
| Actual response approvals executed | 0 | 1 |
| Actual responses submitted | 0 | 1 |
| Passed / failed / unmeasured checks | 134 / 14 / 0 | 141 / 5 / 0 |

Five of the six passing additive checks at each response stage verify that no
action was offered or executed. Only one additive response was actually approved
and submitted. The four passing additive dispositions comprise two accepted
denials, one drafted response, and one human-review disposition. A human-review
pass does not establish successful interpretation of an ambiguous message.

The scoring code reads actual stages and ledger values, requires an executed
response when one is expected, and requires abstention otherwise. Its action
schedule uses offered public actions, not gold. No scoring defect was identified
in this failure accounting. HTTP delivery and absence of real-world effects do
not establish successful adjudication or recovery.

## Remaining additive failures

| Mechanism | Failed disposition checks | Failed action checks | Observed boundary |
| --- | ---: | ---: | --- |
| Late-filing language | 1 | 0 | The whole-reply grammar rejects the claim-bound pronoun form and qualified lateness expression. |
| Qualified invoice-detail request | 1 | 2 | The missing-item target and scoped, modified request do not fit the artifact grammar. |
| Partial-credit language | 1 | 0 | The grant scope and requested-credit noun phrase remain outside the money grammar. |
| **Total** | **3** | **2** | **5 failed checks** |

All three replies have recorded proposal `unknown`. The late-filing case has a
determinate `INELIGIBLE` preflight; the other two have determinate `ELIGIBLE`
preflights. Each remains in `HUMAN_REVIEW`, with no response action offered and no
award recorded. Thus the observed failure occurs before a recognized proposal
can select the implemented denial, artifact, or award branch.

The source explains these boundaries:

- In [`correspondence_language.py`](../../uptime/correspondence_language.py),
  `interpret_factual` line 216 accepts only a past-tense denial followed by a
  possessive claim reference for its linked-pronoun production. `LATE` and
  `PERIOD` at lines 14–15 do not consume additional deadline qualification or a
  second, appositive lateness expression. The broader `DENIAL` vocabulary does
  not extend this separate pronoun production.
- `ARTIFACT` at lines 22–31 lacks payment-status modifiers, an attachment noun
  appended to an invoice-detail noun, and account/month scope suffixes. Both the
  missing-item statement and request must independently resolve through
  `_artifact_target`; recognizing the broad subject does not satisfy the
  whole-message requirement.
- In [`correspondence_reason.py`](../../uptime/correspondence_reason.py),
  `_AWARD` at lines 24–31 permits only particular grant suffixes. `_REQUESTED`
  at line 32 accepts a claim/request amount but not a requested-credit noun
  phrase. These clauses fail before conservation checks at lines 93–99.
  **Present-tense remainder denial is now supported** by `_REMAINDER`; it is no
  longer the remaining monetary-language defect identified in attempt 02.

These findings identify bounded coverage gaps, not a reason to remove
whole-message accounting. Unrelated conditions, ambiguous references, contradictory
amounts, and cross-period assertions must continue to abstain. Incoming language
may propose a factual interpretation; signed terms, receipt scope, evidence, and
the deterministic evaluator remain authoritative.

## Artifact authority is available but was never reached

[`CorrespondenceDesk._reply`](../../uptime/correspondence.py) records
`requested_artifact` only after an `artifact` proposal, at lines 441–445. In both
cohorts' failed artifact workflows, the persisted state has no such request,
despite successful delivery of an artifact and its independent verifier. An
attachment arrival cannot supply the missing interpretation of the vendor reply.

For a separate diagnostic, this review loaded each archived claim's JSON into
memory and supplied only a generic invoice-detail request to
[`approved_artifact`](../../uptime/correspondence_artifacts.py). Both delivered
artifact/verifier pairs resolved successfully; `artifact_conflict` was false.
The immutable database bytes were unchanged afterward. This rules out an
additional demonstrated reference, digest, or verifier mismatch in the immediate
failure. It is not a new response, a modified attempt, or proof that every later
workflow gate would pass.

Public API controls independently demonstrate that an accepted artifact request
can require two distinct sources, reject invalid content/verifier scope, disclose
only a verified artifact reference, and submit a response. They establish the
existing capability without substituting public wording into a private attempt.

## The original cohort retains a separate evidence limitation

Eight original-cohort evaluation checks still return `INSUFFICIENT_EVIDENCE`
because the frozen original filing contents are absent. Two historical denial
checks additionally remain blocked by the requirement for signed, source-defined
filing material, enforced in
[`correspondence_service.py`](../../uptime/correspondence_service.py) lines 39–49.
The original receipts cannot acquire missing historical contents from current
evidence. These ten failed checks remain failed under their original scoring;
preserving the authority boundary is not permission to recategorize them as
successful tasks.

The other four original-cohort failures are the artifact-request disposition and
its two actions, plus the partial-award disposition. They exhibit the parser
mechanisms above. Some cases contain several failed checks, so these are
observation counts rather than additional case denominators. The two historical
denials also record `unknown`; a parser-only correction would not remove their
independent preflight barrier.

No unsafe award or unauthorized response is demonstrated by the remaining
failures. The substantive distinction is between **safe abstention caused by
missing authority** and **safe abstention that misses an otherwise supported
workflow**. Neither establishes vendor generalization or completed recovery.

## Public reproductions and bounded validation

[`scripts/diagnose_socket_03.py`](../../scripts/diagnose_socket_03.py) contains 21
independently written generic probes, using invented monetary and period values.
It has eight accepted-form controls, nine coverage probes, and four refusal
controls. It does not import or open private corpus material, exercise the
application workflow, or rescore any cohort.

```sh
PYTHONDONTWRITEBYTECODE=1 python scripts/diagnose_socket_03.py
```

On source `797c3d0fa1560291cc99d6a08a7b8bacbbb1d344`, the diagnostic reports
**12 passed, 9 failed, 0 control/refusal failures**, and exits **1**. The failing
probes separately isolate tense, determiner, deadline qualification, redundant
same-ground qualification, artifact attachment nouns, payment modifiers, scoped
requests, scoped grants, and requested-credit nouns. Its nonzero exit deliberately
reports unresolved coverage; there is no expected-failure exemption or altered
cohort gold.

The following existing public checks passed in the same checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  tests/test_correspondence_language_56.py \
  tests/test_correspondence_service.py::test_correct_denial_of_independently_witnessed_original_requires_actual_signed_ground \
  tests/test_correspondence_service.py::test_separately_delivered_response_uses_approved_scope_and_preserves_partial_ambiguity \
  tests/test_correspondence_resource.py::test_named_and_typed_supporting_artifacts_require_two_sources \
  tests/test_correspondence_resource.py::test_private_content_digest_and_independent_verifier_scope
```

Result: **124 passed in 7.44 seconds**; one existing Starlette/httpx deprecation
warning. Commands used the existing shared Python environment, with no dependency
installation or network. This was a bounded verification run, not the full merge
suite. Only documentation and this diagnostic script were added.

## Preserved provenance

Both reports identify source `797c3d0fa1560291cc99d6a08a7b8bacbbb1d344`, stable
application tree hash
`a62bace9e77f82ae1c1ecd167277914b7c56260868bbcac920fde13e3460d1e2`, and harness hash
`90a92a1c15696cab53db4ff7689f39f84e01e59057c9b4201ac62c61c9190f85`.

| Preserved artifact | SHA-256 |
| --- | --- |
| Original attempt 03 public report | `a61b85134cfcc3b7097ce29e64c0314828a3da553965937029a81819a8592f7a` |
| Additive attempt 03 public report | `7f26abc04a34cfec7acffe4304b3e513e6a07732571c69c5e4c621aeecf8df01` |
| Original observation transcript | `0b321a8f2eeda86d4d24f049e184e4609a6071bd55a554150385b1dcdb0bc3ff` |
| Additive observation transcript | `7f497727f91553918a65ab67f3c3282a112243334db6af260c20308e50715d18` |
| Original freeze manifest | `d0bcd1c0ea598e521bc221c10f95b810a48ee97a69bf36d4cf6f31c7c892e58c` |
| Additive freeze manifest | `3878dc445d082ea2d51aa065dc17fe45d24dd52bbb1c25dc49c8aa30a8420688` |

The input and gold byte commitments were checked against both manifests without
reading gold into the diagnostic or altering it. The shared public source remains
`697b2b662246f6f08672cb23d59ca03cadfa506f117947ff12debd063e258cc1`; extraction
`7da3ba6910779918cc15c2fe82ea79f0f8fece3ac58348f020b3824fba7754c4`.

These remain **studied, in-family `SCRIPTED_TEST` results**, with automated named
reviewer credentials and no human approval. Existing attempts and original
denominators remain intact. Only a separately preserved future socket attempt
can establish whether subsequent language changes complete these workflows.
