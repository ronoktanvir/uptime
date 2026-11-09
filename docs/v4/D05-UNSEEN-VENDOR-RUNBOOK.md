# D05 unseen-vendor proof: operator runbook

The ordinary application path for the D05 proof ([decision 97](decisions/ADR-0097-automatic-family-selection.md)): Uptime selects the rule family from an independently selected public source, and a person approves before activation. Setup follows [the public proposal runtime](PUBLIC-PROPOSAL-RUNTIME.md).

**Roles (set 2026-11-09):**
- **gent8 (verification lane):** selects one public vendor SLA by its pre-registered rule, not from corpus84, and runs the steps below. The vendor is not disclosed to W3 beforehand.
- **Operator:** approves the exact model requests.
- **Ronok:** performs the interpretation acceptance, promotion and rollback himself. Nobody signs or acts in his name.

**D10:** only the public source text goes to the model. The customer overlay is private and is never part of a model request.

## Before the run

1. Phase 2 must be merged: candidate staging accepts only the automatically selected job, and the browser has no profile select. Otherwise an operator-chosen profile could still stage a candidate, and the run would not count as D05 evidence.
2. Save the public source exactly as published (UTF-8 text; never reformat it) and record its URL and SHA-256. The application JSON document uses `classification: "public"`, the published URI, a name, and the exact text.
3. Start the local server with the protected `--public-proposal-config` (vendor kind enabled) and an empty approval catalog.

## Steps

1. **Vendors → Generate a public proposal.** Enter a new lowercase vendor identifier, the document name, URI, origin "Public document" and the exact text, then choose **Check generation access**.
   - `SELECTED` with method `deterministic_document_parser`: the deterministic parser recognized a canonical monthly source, and no model call is needed. Go to step 4.
   - `APPROVAL_REQUIRED`: the view lists the family requests awaiting approval. Continue with step 2.
2. **Approve every family request offline.** Use the same tenant, account, vendor identifier and attempt identifier as the browser:

   ```bash
   uv run --locked python scripts/public_proposals.py export-vendor --profile auto --document /public/vendor.json --config /protected/config.json --output /protected/exports/unseen.json --tenant WORKSPACE --subject ACCOUNT --target VENDOR_ID
   ```

   This writes `unseen.monthly-propositions.json` and `unseen.resource-month.json` and prints each complete request SHA-256. Review each with `show`, then `approve` each separately with its own `--expected-request-sha256` and `--confirm-authored-public`. Export makes no model call. Approval grants model invocation only, not review or activation.
3. **Generate proposals.** Choose **Check generation access** again (outcome `NOT_SUBMITTED`), then **Generate proposals**. Both family jobs are queued together, each called at most once. When the page says every family evaluation has finished, choose **Refresh proposal status**.
4. **Read the outcome:**

   | Outcome | What to do |
   |---|---|
   | `SELECTED` | The page shows the selected family and why every other family was refused. Stage the candidate with the private customer overlay. It enters SHADOW only. |
   | `NO_SUPPORTED_FAMILY`, `AMBIGUOUS` or `INCOMPLETE` | Record the outcome and its review requirements verbatim. That is the result. Do not choose a family by hand or edit the source to make it pass. |

5. **Review in SHADOW:**
   - `GET /api/vendors/{id}/requirements` shows the requirement card, generated drafts, and `family_selection`.
   - A reviewer authors independent tests from the cited clauses. The drafts are not the tests, and reuse of draft facts is flagged.
6. **Ronok acts himself:** accept or reject the source interpretation, approve, activate, inspect the audit, then roll back. These are his signed actions and cannot be scripted.

## Record for the evidence receipt

- **Source:** URL, SHA-256 and retrieval time.
- **Attempt:** vendor identifier, attempt identifier, `selection_sha256`, and each family's job id, status and refusal codes.
- **Model calls:** Claude Code session ids and cost, from the job receipts.
- **Adapter:** version, revision and audit entries for interpretation, approval, activation and rollback, with the acting account and time.

## Claim limits

- One source is one observation. It is not a reliability rate.
- A refusal is a correct refusal only if the stated reason is right.
- The evaluation 84 first-attempt score (0/4) is unchanged by this run.
