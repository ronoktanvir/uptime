# Existing-test change ledger

This ledger records presentation and fixture changes for the Northwind walkthrough and related correctness work. A changed expectation must have a stated behavioral reason; a failed private evaluation is never rewritten into a pass. New tests are reported separately in workstream validation records.

| Workstream | Exact test names and reasons | Integration status |
| --- | --- | --- |
| Clean finance views | `TEST-CHANGES-UI.md` in the UI branch lists the affected presentation assertions. Root will link it after integration. | Pending |
| Semantic source bindings | [TEST-CHANGES-61.md](TEST-CHANGES-61.md) lists every changed fixture/assertion, including the public inbox controls, six historical-award parameters and stricter draft-only monetary behavior. | Merged at `aafd093`; first full run had 8 failures. Root corrections pass all 46 affected tests; full rerun pending. |
| Dispute interpretation and public model transport | [TEST-CHANGES-60-62.md](TEST-CHANGES-60-62.md) records that no pre-60 test assertion was changed. New tests exercise the added bridge and transport boundaries. | Integrated at `f83587f`; 2,684 passed, 1 warning. First disk-full failure preserved. |
| Northwind inputs and continuous flow | New fixture and workflow tests are being implemented. No existing expectation has been changed by root at this checkpoint. | Pending |

Every merge requires `uv run --locked pytest`. Use a unique temporary base directory for concurrent suites, preserve the first failure output, and record subsequent results without overwriting earlier evidence.

Decision67 adds `test_semantic_current_projection.py` for four independently reproduced failures and five additional containment controls. It changes no existing test assertions. The source review and failed evidence remain in [the independent report](evidence/semantic-61-independent/review.json); the repair decision is [ADR67](decisions/ADR-0067-current-semantic-containment.md).
