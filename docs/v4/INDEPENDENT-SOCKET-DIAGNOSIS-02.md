# Socket attempt 02: filing works; reply interpretation remains incomplete

The plan-reference correction removes the previous filing blockage, but it does
not establish successful denial handling. All scheduled observations are now
measured. The additive cohort still passes only **1/7 denial dispositions**:
the six failures all reach a clean financial preflight and then produce the
parser proposal `unknown`. The remaining immediate failure is conservative
language-parser undercoverage for already implemented workflow categories.
There is no evidence here of an arithmetic error or a missing contractual
operator, and an unknown proposal does not authorize a response or an award.

This is a separate diagnosis of preserved socket attempt 02. It does not replace
[attempt 01's diagnosis](INDEPENDENT-SOCKET-DIAGNOSIS.md), alter gold, reinterpret
missing historical evidence as adequate, or claim that a future parser change
will pass the frozen cohort. No product or harness change was made in this review.

## What now delivers

| Measurement | Original frozen cohort | Separate additive cohort |
| --- | ---: | ---: |
| Complete cases | 2/10 | 2/8 |
| Evaluation expectations | 2/10 | 8/8 |
| Original-filing observations | 5/5 | 7/7 |
| Denial deliveries | 5/5 | 7/7 |
| Denial dispositions | 1/5 | 1/7 |
| Frozen artifact delivery | 1/1 | 1/1 |
| Response-approval expectations | 0/1 | 5/7 |
| Response-submit expectations | 0/1 | 5/7 |
| Passed / failed / unmeasured observations | 134 / 14 / 0 | 136 / 10 / 0 |
| Measured / required observations | 148/148 | 146/146 |

The five additive response-stage passes are checks that no action was offered or
executed where no response was expected. **No additive response was executed.**
The two cases that require a response fail both action stages. The lone passing
denial disposition is the requested human-review outcome; it does not show that
the parser understood an ambiguous message. Delivered historical originals are
observed receipts, not newly executed local filings. HTTP 200 still establishes
intake rather than correct adjudication.

Relative to attempt 01, all nine originally unmeasured original-cohort observations
and all seventeen unmeasured additive observations are measured. The increased
number of measured failures is therefore not evidence that the plan correction
introduced a regression. The earlier reports retain their original denominators
and results.

## Causal classification

Read-only inspection of the archived observations and databases gives this
additive failure accounting. Categories describe mechanisms, not private text.

| Reply category | Failed denial dispositions | Failed action observations | Confirmed parser boundary |
| --- | ---: | ---: | --- |
| Availability assertion | 3 | 2 | Period modifiers and an explicit decimal percentage are outside the accepted grammar. |
| Late-filing assertion | 1 | 0 | A linked pronoun and additional deadline qualification are not consumed by the full-clause grammar. |
| Invoice-detail request | 1 | 2 | A declarative missing-item assertion and qualified request do not match the request grammar. |
| Partial credit grant | 1 | 0 | Claim-scoped grant suffix, requested-credit wording and present-tense remainder denial are outside the monetary clause grammar. |
| **Total** | **6** | **4** | **10 failed observations** |

The relevant code is
[`correspondence_reason.propose`](../../uptime/correspondence_reason.py) and
[`correspondence_language.complete_explanation`](../../uptime/correspondence_language.py).
There are two separate language gates: finding a candidate reason, then requiring
every substantive clause to fit that reason. For example, the availability cue's
`[^.!?]` spans stop at the decimal point in a numeric threshold; its complete-clause
pattern also has no numeric-percentage production. Fixing only one gate would
leave the other unchanged. A monthly modifier can pass the cue but fail the
complete-clause check.

The artifact request reaches the same `unknown` boundary before the desk records
`requested_artifact`. Later delivery of a valid attachment cannot create that
missing request interpretation. In a read-only, in-memory diagnostic,
[`approved_artifact`](../../uptime/correspondence_artifacts.py) resolves each
cohort's actual delivered artifact/verifier pair when supplied a generic
invoice-detail request. Thus there is no demonstrated additional source-reference
or digest mismatch behind this immediate parser failure. This diagnostic is not
an executed response and does not substitute a new request into any attempt.

The monetary parser already reconciles a labeled award, original request and
remainder. Its `_AWARD`, `_REQUESTED` and `_REMAINDER` productions reject the
observed wording before that reconciliation can yield an award. In particular,
`_REMAINDER` includes `denied`, `decline` and `declined`, but not `deny`. The public
reproduction below separates these failures one at a time using new amounts.

These are product coverage limitations with safe abstention, rather than an
unsafe financial decision or evidence that these business workflows are absent.
The existing authenticated public controls establish the latter distinction:
correct threshold/late denial, mistaken threshold response, partial award,
ambiguity, and independently verified artifacts all work with accepted wording.
No scoring defect was found in these failed observations. The scorer checks the
actual disposition and ledger, and deliberately distinguishes an absent action
from an executed response.

The original cohort retains its separate inadequate-evidence problem: eight
failed evaluation observations lack the required original filing contents, and
two historical-denial checks still lack signed source-defined filing material.
Those ten failed observations cannot be made valid merely by recognizing more
language. Its other four failures are one artifact-request disposition, two
associated response-action checks and one partial-award disposition, with the
same parser mechanisms described above. This is an observation-level accounting;
some cases have more than one failed observation.

## Public minimal reproductions

The following new synthetic probes use the committed Compass agreement's public
98.75% threshold and USD 20.99 claim amount, with an invented USD 7.00 partial
award. They contain no private cohort text or gold. A baseline demonstrates that
the workflow category is recognized, while each variant isolates a rejected
language feature. Parser recognition alone is not authorization or a full API
workflow result.

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --locked python - <<'PY'
from decimal import Decimal
from uptime.correspondence_reason import propose

probes = [
    ('availability baseline', 'Denied. Availability met the threshold.'),
    ('monthly modifier', 'Denied. Monthly availability met the threshold.'),
    ('numeric threshold', 'Denied. Availability met the 98.75% threshold.'),
    ('lateness baseline', 'We reject the claim because the claim was filed late.'),
    ('linked pronoun', 'We reject the claim because it was filed late.'),
    ('deadline modifier', 'Denied. The claim was filed after the contractual deadline.'),
    ('artifact baseline', 'Please provide the invoice detail.'),
    ('missing assertion', 'Invoice detail is missing. Please provide the invoice detail.'),
    ('paid modifier', 'Please provide the paid invoice detail.'),
    ('award baseline', 'We grant a service credit of USD 7.00. The original claim was USD 20.99. We denied the remaining USD 13.99.'),
    ('award scope suffix', 'We grant a service credit of USD 7.00 for this claim.'),
    ('requested-credit wording', 'We grant a service credit of USD 7.00. The original requested credit was USD 20.99.'),
    ('present-tense denial', 'We grant a service credit of USD 7.00. We deny the remaining USD 13.99.'),
]
for label, text in probes:
    result = propose(text, claimed=Decimal('20.99'))
    print(f'{label}: {result.reason}' + (f' {result.amount}' if result.amount else ''))
PY
```

Observed on application `877f427a9a22ae8d8160616c042277ff347d02e3`:

```text
availability baseline: availability
monthly modifier: unknown
numeric threshold: unknown
lateness baseline: time_bar
linked pronoun: unknown
deadline modifier: unknown
artifact baseline: artifact
missing assertion: unknown
paid modifier: unknown
award baseline: award 7.00
award scope suffix: unknown
requested-credit wording: unknown
present-tense denial: unknown
```

Nine existing authenticated public checks also passed on this source:

```sh
uv run --locked pytest -q \
  tests/test_correspondence_service.py::test_correct_denial_of_independently_witnessed_original_requires_actual_signed_ground \
  tests/test_correspondence_service.py::test_separately_delivered_response_uses_approved_scope_and_preserves_partial_ambiguity \
  tests/test_correspondence_resource.py::test_named_and_typed_supporting_artifacts_require_two_sources
```

These controls use the repository's fixture authority and TestClient; they do not
replace the actual socket cohort results. The diagnostic probes and these nine
checks ran with the existing locked environment using `--offline --no-sync`.

## Provenance and next decision

Both socket reports name source `877f427a9a22ae8d8160616c042277ff347d02e3`,
application tree hash
`950c687c4c16603ba05dc711be076460dce4c3bf12533eb925ad07b91b396bd7`,
and unchanged harness hash
`90a92a1c15696cab53db4ff7689f39f84e01e59057c9b4201ac62c61c9190f85`.
The public agreement hash remains
`697b2b662246f6f08672cb23d59ca03cadfa506f117947ff12debd063e258cc1`,
and the extraction hash remains
`7da3ba6910779918cc15c2fe82ea79f0f8fece3ac58348f020b3824fba7754c4`.

| Preserved artifact | SHA-256 |
| --- | --- |
| `adequate-original-socket-02.json` | `98810ec2f44a10b7cb294a536c2d0c3c9bbec5f6ae3921f1058e459573cea0c4` |
| `adequate-additive-socket-02.json` | `b0cd309ad5a29588840592a33dc433b04d936a8f0c7aee493e8c993351df5f49` |
| Original observation transcript | `4f8e86b5494121e0e54a6bc9507313b1e47e4701fa0a815e3f5acdd2feccee93` |
| Additive observation transcript | `6e7a04a0297dad8c0677105dadd560bfd79b9b49ac8a82b074a350dae806f3a7` |
| Original freeze manifest | `d0bcd1c0ea598e521bc221c10f95b810a48ee97a69bf36d4cf6f31c7c892e58c` |
| Additive freeze manifest | `3878dc445d082ea2d51aa065dc17fe45d24dd52bbb1c25dc49c8aa30a8420688` |

Both freeze manifests verify. Private inputs, gold, signatures, source copies and
attempts remain outside the repository. No private text was sent to an external
model. These remain studied in-family, `SCRIPTED_TEST` observations rather than
vendor-population generalization or human approval.

Any next correction should be framed as a bounded language-coverage change with
public positive and adversarial controls. It must continue to account for every
substantive clause, bind pronouns and scoped award language to the actual receipt,
retain ambiguity and unrelated-condition refusal, and reconcile every monetary
figure. Numeric threshold language needs an explicit interpretation against the
reviewed terms; it must not silently become a new contractual threshold. Existing
whole-message coverage cannot simply be removed. Only a new preserved socket
attempt can establish the resulting cohort dispositions and executed responses.
