# Decision 61 test change ledger

Baseline is integrated `704caa5` (2,607 passing tests). Original extraction refusals, preregistered cases, source documents and historical receipts are unchanged. New tests use public synthetic inputs; no private heldout oracle or expected output was consulted. No deadline, numerical tolerance, assertion-wide bypass or automatic production approval was added.

## Existing setup changes

| File and exact function/fixture | Change and reason | Preserved assertions |
| --- | --- | --- |
| `test_vendor_resource.py::result` | Arithmetic/evidence tests explicitly receive a synthetic named `reviewed_context` pinned to their compiled manifest and bound overlay. Unreviewed meaning tests call production `evaluate` directly. | Existing numerical, fee, interval, deadline and issuance assertions. |
| `test_vendor_resource.py::test_review_gate_and_transaction_scoped_active_resolution` | Record explicit source/literal review before independent tests. | Inactive refusal, required interpret/approve/activate chain, $12.51, citation and transaction assertions. |
| `test_vendor_resource_operators.py::test_ungrouped_text_requires_case_distinction_and_explicit_recorded_formula_decision` | Record explicit semantic review before the existing formula interpretation gate. | Formula alternatives, independent scenarios and explicit final decision remain required. |
| `test_vendor_service_month.py::run` | Supply scoped synthetic semantic review before fee-category interpretation. | Aggregate thresholds, fractional minutes, fee math, evidence and date assertions. |
| `test_vendor_service_month.py::test_service_aggregate_signed_api_produces_case_and_rollback` | Pass an explicitly constructed synthetic semantic review to the real-loopback rehearsal. The script accepts it separately and never creates it from expected scenarios. | $20.99, scripted authority label, rollback denial and preserved provenance. |
| `test_correspondence_resource.py::install` | Use the new signed semantic-review API before tests. | Shared signed resource lifecycle, evidence, fee, region, obligation and correspondence assertions. |
| `test_correspondence_service.py::service` | Use the new signed semantic-review API before tests. | Shared signed aggregate lifecycle and independently received reply assertions. |
| `test_correspondence_filing_refs.py::filing` | Use the new signed semantic-review API before tests. | Fee/plan reference negatives, original receipt provenance, amounts and exact diagnostic assertions. |
| `test_correspondence_resource.py::test_distinct_filing_items_reference_only_their_provenance` | Add the tested field names to an explicit synthetic source clause and review their literal representations. The old helper supplied names that were absent from the contract. | All five original reference/denial assertions remain unchanged. |

## Existing assertion changes

| Exact test | Before → after | Reason |
| --- | --- | --- |
| `test_vendor_resource.py::test_contractual_negative_controls` (`cosmetic display delay` parameter only) | `INELIGIBLE` → `INSUFFICIENT_EVIDENCE`; amount remains `None`. | An unknown observation cannot establish a proven zero outage. This is the approved unresolved-meaning boundary. |
| `test_vendor_resource.py::test_stable_service_predicate_identifier_requires_literal_source_grounding` (`sample_loss` raw-string assertion only) | `$12.51` → `None`. | The original assertion exercised the opaque-ID/raw-literal union that decision 61 removes. The same contract's reviewed literal positive control still yields $12.51. |
| `test_v4_authority.py::test_human_database_contains_only_public_verifier_and_it_cannot_sign` | Expected columns add `schema_epoch`. | Additive startup fence, while verifier equality, no private key, inability to sign and legitimate signed request checks remain unchanged. |

## New controls

`test_vendor_semantic_bindings.py` checks full-source pins, exact occurrences, bounded whitespace, role separation, arbitrary explicitly reviewed external representations, no label-to-observation inference, strict boolean attestations, live revocation and incomplete review. `test_vendor_binding_integration.py` executes the frozen public refusal cases, demonstrates the $12.51 error when the removed union is deliberately restored in memory, and checks signed claim revocation, current rollup suppression, unchanged evidence/receipts and stable economic reservations after re-review. `test_semantic_schema_epoch.py` checks preserved authority/receipt bytes, idempotent migration and refusal of an unknown authority schema.

The preregistered typed-wire-reference positive and typed-reference-specific gate cases remain deferred by root's explicit decision; the signed wire is unchanged. Their literal-context analogues are tested, but they are not reported as implementation of a typed wire. Named review remains a human judgment boundary: token spans and attestations cannot independently prove that a reviewer interpreted a conditional or negated clause correctly.

The new review fixture explicitly binds the ordinary aggregate test's `subscription` category to its supported source fee-basis clause. This does not infer a category from expected money. Production requires its own explicit `fee_inclusions` selections whenever fee exclusions exist; an unfamiliar category cannot become included merely by failing to match a reviewed exclusion. Unknown filing-name literals also remove monetary intermediate values already calculated before the filing check.
