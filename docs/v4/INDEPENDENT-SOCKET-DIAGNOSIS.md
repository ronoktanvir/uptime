# Independent diagnosis of the adequate socket attempts

The unchanged workflow counts have a specific remaining cause: **the aggregate
`plan` field accepts only the literal plan name, while the frozen filing packets
cite the signed invoice that contains that plan.** The service and fee-reference
repair did not change this branch. All seven additive filing packets still fail
this one field; their other supplied fields pass the repaired resolver. This is a
confirmed reference-representation mismatch, not evidence that the plan is absent
or that the agreement requires an unsupported contractual operator.

This review made no product, harness, gold, input or scoring changes. It inspected
the actual socket observations and read the archived databases in SQLite read-only
mode. The public reproduction below uses only committed synthetic Compass data.
No private case text, identifiers, amounts, signatures or gold are reproduced.

## Results and provenance

These are the existing socket results, not a new exercise or rescore:

| Cohort | Complete cases | Evaluation | Denial dispositions | Passed / failed / unmeasured observations |
| --- | ---: | ---: | ---: | ---: |
| Original frozen | 2/10 | 2/10 | 0/5 | 126 / 13 / 9 |
| Separate additive | 1/8 | 8/8 | 0/7 | 122 / 7 / 17 |

Both ran against application `f56e067d4f747eedbc9e3a3e4ee117f644a8378b`,
which contains the `92b1ca1` filing-reference repair. The diagnostic checkout is
`38bca3e2f2d4e1d691cd022d60d21c62b12013da`; the relevant resolver, join and
projection files have no diff between those revisions. The socket reports record
stable application tree hash
`ed98527dd85ad507410a096bed52984a7e634455b3f9a3f0cec30bc243311e5f`
and harness hash
`90a92a1c15696cab53db4ff7689f39f84e01e59057c9b4201ac62c61c9190f85`.
The studied public agreement remains source hash
`697b2b662246f6f08672cb23d59ca03cadfa506f117947ff12debd063e258cc1`;
the extraction hash is
`7da3ba6910779918cc15c2fe82ea79f0f8fece3ac58348f020b3824fba7754c4`.

| Preserved artifact | SHA-256 |
| --- | --- |
| `adequate-original-socket-01.json` | `c508a99fec80bc59037f46d29c924a0ab42b95d719a3d1f49cbb7b93e0a574b1` |
| `adequate-additive-socket-01.json` | `2e96c146aedd64f818dbdab7ac643b868b7e0b378e894aab726d99a83d01ea54` |
| Original observation transcript | `489240da6da784f82f5dfa7b0093d3aa8277fcc7db38bcac135f95227352508a` |
| Additive observation transcript | `deb0d8bef55733781e99abe5c95be2506c25d17e44ad4127063e01fffa732155` |
| Original freeze manifest | `d0bcd1c0ea598e521bc221c10f95b810a48ee97a69bf36d4cf6f31c7c892e58c` |
| Additive freeze manifest | `3878dc445d082ea2d51aa065dc17fe45d24dd52bbb1c25dc49c8aa30a8420688` |

Both freeze manifests still verify. The report files and private transcripts stay
in their existing operator-owned locations. These are studied fictional,
in-family cases with `SCRIPTED_TEST` authority and `human_approval=false`.
Neither the original first pass nor its denominator is replaced.

## Mechanism and classification

1. [`projection.filing_fields`](../../scripts/adequate_holdout/projection.py)
   explicitly produces `plan` with `refs=[invoice_body['source_ref']]`.
   The additive packets already contain this representation in their frozen
   filing material; the runner forwards those supplied fields unchanged.
2. [`join_service`](../../uptime/correspondence_service.py) first verifies both
   signed records' plan against the reviewed overlay, complete flags, timestamps
   and content commitments. Thus it has independent plan-bearing source records
   before checking filing fields.
3. [`filing_refs`](../../uptime/correspondence_resource.py) accepts actual source
   and event IDs for aggregate service/product fields. Its plan/edition branch
   still returns only `{overlay['plan']}`. The signed invoice ID passes the public
   `FilingField.refs` identifier schema but fails this semantic reference set.
4. `join_service` requires every field to resolve. The remaining plan mismatch
   raises `Each filing field must identify its independently supported source
   record.` and withholds the complete filing packet. The existing repair's
   [`FIELDS` regression](../../tests/test_correspondence_filing_refs.py) contains
   service and two fee fields, but no plan field; those tests therefore did not
   cover this residual mismatch.

The seven additive failures separate into four ordinary originals blocked before
any denial is delivered, and three historical originals whose denials enter the
normal event API but remain `HUMAN_REVIEW` with that same preflight error. The
three original-cohort ordinary submissions have the same plan-only mismatch.
These observations explain why the service/fee repair can work and still leave
the aggregate cohort counts unchanged. HTTP 200 on event intake establishes
receipt, not an accepted denial or a completed dispute workflow.

The original cohort also has a distinct evidence problem: all eight failed
evaluation observations report `Required claim contents are absent from the
verified original filing.` Its two delivered historical-denial checks report
`Awaiting signed source-defined filing contents.` Those ten failed observations
cannot be repaired by reconstructing past contents from a present invoice. The
two deliberate missing-evidence controls remain separate and passing. Existing
gold remains unchanged even where it assumes adequate historical proof.

The narrow classification is **a product/harness reference contract mismatch**.
A literal plan is a usable representation for this public synthetic example, so
this is not the same impossibility as a spaced service name rejected by `Id`.
However, changing historical invoice references to plan literals would change the
asserted filing contents. The bounded product correction to consider is accepting
references to the exact already-validated aggregate records that attest the plan,
with existing scope, completeness and mismatch checks intact. It does not require
new entitlement arithmetic or a relaxed wire identifier type. No correction or
successful downstream outcome is established by this review.

## Public reproduction

Run from the repository with the locked environment. This diagnostic adds a plan
filing requirement to the committed synthetic Compass agreement and uses its
existing monthly records. It validates each request against the actual wire
schema, then exercises the unmodified join. It creates no claims or receipts and
is not an end-to-end or signature-ingress test; the preserved socket transcripts
supply that separate observation.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests uv run --locked python - <<'PY'
from uptime.contracts import fingerprint
from uptime.correspondence_resource import filing_refs
from uptime.correspondence_service import join_service
from uptime.correspondence_types import Delivery, Scope, instant
from test_vendor_service_month import OVERLAY, ROWS, manifest
from test_correspondence_service import reports

channel = 'claims@example.invalid'
contract = manifest(ROWS + [
    ('Send claims to claims@example.invalid. Include plan.',
     {'submission_channel': channel, 'request_fields': ['plan']})])
scope = Scope(account=OVERLAY['account'], vendor='Heliograph Navigation',
              contract=OVERLAY['agreement'], service=OVERLAY['product'],
              component='public-control', invoice='invoice-7',
              incident='public-control', currency='USD', month='2027-02',
              region='global')
events = []
for role, body in reports():
    event_id = 'diagnostic-' + body['kind']
    Delivery.model_validate(dict(event_id=event_id,
                                 scope=scope.model_dump(), body=body))
    events.append(dict(event_id=event_id, source=role.removesuffix('-fixture'),
                       body=body, kind=body['kind'], digest=fingerprint(body)))
groups = {e['kind']: e for e in events}
print('allowed plan references:', sorted(
    filing_refs('plan', contract, OVERLAY, scope, groups, [], [])))
for reference in ['invoice-7', 'status-7', 'Marine']:
    body = dict(kind='filing_material', source_ref='plan-material',
                observed_at='2027-03-03T00:00:00Z', channel=channel,
                fields=[dict(name='plan', refs=[reference])])
    Delivery.model_validate(dict(event_id='plan-material',
                                 scope=scope.model_dump(), body=body))
    material = dict(event_id='plan-material', source='customer',
                    kind='filing_material', body=body, digest=fingerprint(body))
    try:
        join_service(scope, events + [material], contract, OVERLAY,
                     instant('2027-03-03T00:00:00Z'), [])
        print(reference, 'JOINED')
    except ValueError as error:
        print(reference, str(error))
PY
```

Observed on the diagnostic base:

```text
allowed plan references: ['Marine']
invoice-7 Each filing field must identify its independently supported source record.
status-7 Each filing field must identify its independently supported source record.
Marine JOINED
```

A repair needs its own public synthetic positive and wrong-plan/wrong-source
controls, followed by new immutable socket attempts. Until those attempts measure
the later stages, denial interpretation, evidence cures and partial-award handling
remain unresolved for these cohorts. Preserve 0/7 and every unmeasured stage in
these existing reports.
