# Existing-test change ledger

This ledger records presentation and fixture changes for the Northwind walkthrough and related correctness work. A changed expectation must have a stated behavioral reason; a failed private evaluation is never rewritten into a pass. New tests are reported separately in workstream validation records.

| Workstream | Exact test names and reasons | Integration status |
| --- | --- | --- |
| Clean finance views | [UI ledger](TEST-CHANGES-UI.md) lists every affected presentation assertion by exact test name, including the final removal of classifications from expandable details. | Pending |
| Semantic source bindings | `TEST-CHANGES-61.md` in the onboarding branch lists explicit semantic-review fixture setup and stricter monetary behavior. Root-owned draft-only and cross-service joins remain to be updated explicitly. | Pending |
| Dispute interpretation and public model transport | `TEST-CHANGES-60-62.md` records that no pre-60 test assertion was changed. New tests exercise the added bridge and transport boundaries. | Pending |
| Northwind inputs and continuous flow | New fixture and workflow tests are being implemented. No existing expectation has been changed by root at this checkpoint. | Pending |

Every merge requires `uv run --locked pytest`. Use a unique temporary base directory for concurrent suites, preserve the first failure output, and record subsequent results without overwriting earlier evidence.
