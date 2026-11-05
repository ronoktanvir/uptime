# Existing-test change ledger

This ledger records presentation and fixture changes for the Northwind walkthrough and related correctness work. A changed expectation must have a stated behavioral reason; a failed private evaluation is never rewritten into a pass. New tests are reported separately in workstream validation records.

| Workstream | Exact test names and reasons | Integration status |
| --- | --- | --- |
| Clean finance views | [UI ledger](TEST-CHANGES-UI.md) lists every affected presentation assertion by exact test name, including classifications formerly shown in expandable details. | Integrated from `ab9d612`; 46 focused Node checks and authored/actual-projection browser checks passed. Joined full suite pending. |
| Semantic source bindings | [TEST-CHANGES-61.md](TEST-CHANGES-61.md) lists every changed fixture/assertion, including the public inbox controls, six historical-award parameters and stricter draft-only monetary behavior. | First full run had 8 failures; corrected run2751passed. Independent findings repaired at `e365f52`:2760passed1warning, independent recheck passed. |
| Dispute interpretation and public model transport | [TEST-CHANGES-60-62.md](TEST-CHANGES-60-62.md) records that no pre-60 test assertion was changed. New tests exercise the added bridge and transport boundaries. | Integrated at `f83587f`; 2,684 passed, 1 warning. First disk-full failure preserved. |
| Northwind inputs and continuous flow | [Workflow ledger](TEST-CHANGES-66.md) records new composition tests and preserved shared assertions. Source-quantity/governing-fee tests are new; current-authority repairs and April integration remain under independent review. | Posted-credit composition integrated at `4cf1eaf`: 2,858 passed, 1 warning. Complete application proof pending. |

Every merge requires `uv run --locked pytest`. Use a unique temporary base directory for concurrent suites, preserve the first failure output, and record subsequent results without overwriting earlier evidence.

Decision67 adds `test_semantic_current_projection.py` for four independently reproduced failures and five additional containment controls. It changes no existing test assertions. The source review and failed evidence remain in [the independent report](evidence/semantic-61-independent/review.json); the repair decision is [ADR67](decisions/ADR-0067-current-semantic-containment.md).
