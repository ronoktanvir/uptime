# Automatic family selection: application interface (D05)

The browser contract for [decision 97](decisions/ADR-0097-automatic-family-selection.md). Server: W3. Browser (`web/v4_ui.js`): W7. Phase 2 server enforcement (`work/onboarding-d05-phase2-89`) must merge **together with** the browser change below. Without the browser change, the profile-select interface can no longer stage a candidate.

## Requests

All routes already exist and are draft-signed. The client never names a family.

| Step | Request | Effect |
|---|---|---|
| Inspect / refresh | `POST /api/vendors/{id}/proposal-access` `{"document": {...}, "profile": "auto", "attempt_nonce": "initial"}` | Read-only selection view. No provider call; repeatable. |
| Start | `POST /api/vendors/{id}/proposal-jobs` (same body) | Queues one job per family, only when every family request is approved. Returns the same view. Idempotent. |
| Poll | `GET /api/vendors/{id}/proposal-jobs/{job_id}` per family job, or re-post the inspect request | Until the outcome is terminal. |
| Stage (model-selected) | `POST /api/vendors/{id}/proposal-jobs/{selected.job_id}/candidate` `{"overlay": {...}}` | SHADOW only. Any other job is refused with HTTP 409 and the requirement text. |
| Stage (offline-selected) | `POST /api/vendors/{id}/candidates` `{"document": {...}, "overlay": {...}}` | SHADOW only. |
| Explain at review | `GET /api/vendors/{id}/requirements` → `family_selection` | How the installed artifact's family was chosen and why other families lost. |

## Selection view

```
{ "outcome": "SELECTED" | "AMBIGUOUS" | "NO_SUPPORTED_FAMILY" | "INCOMPLETE" | "PENDING"
             | "NOT_SUBMITTED" | "APPROVAL_REQUIRED" | "PROVIDER_UNCONFIGURED",
  "selected": {"family", "method": "deterministic_document_parser" | "public_proposal_job", "job_id" | null} | null,
  "offline": {"accepted", "reason"},
  "families": [{"family", "label", "state", "enabled", "approval_reason",
                "job": <GET proposal-jobs/{job} projection> | null,
                "refusal": {"codes", "explanations", "passages", "missing_terms"} | null,
                "attempts": {"total", "validated", "structural_refusals"}}],
  "review_requirements": ["..."], "selection_sha256": "...",
  "authority": {"approval_gate": false, "dispatch_authorized": false} }
```

Family states: `VALIDATED`, `REFUSED_STRUCTURAL`, `REFUSED_READING`, `NOT_EVALUATED`, `INCONCLUSIVE`, `PENDING`, or `null` (not submitted).

## Browser change (implemented by W3 on `work/onboarding-d05-ui-89`; gent7 reviews)

1. Remove the required "Extraction profile" select and send `"profile": "auto"`.
2. Render the selection view:
   - the outcome;
   - `review_requirements`, verbatim;
   - each family's state and refusal (the existing refusal-diagnostic rendering applies per family);
   - when the outcome is `APPROVAL_REQUIRED`, which family requests still need operator approval.
3. On `SELECTED`, offer staging through the route for its `method`. Show no staging control for any other outcome.
4. Optionally show `family_selection` beside the approve controls.

Tests moved to the automatic flow with the browser change (see the W3 ledger):
- `tests/test_vendor_auth83.py::test_expired_browser_session_recovers_same_job_without_resubmitting`
- `tests/test_vendor_model_jobs_browser.py::test_browser_checks_permission_generates_and_stages_separate_overlay[manual]`
- `tests/test_vendor_model_jobs_browser.py::test_browser_checks_permission_generates_and_stages_separate_overlay[utf8_file]`
- the `.cjs` helpers that select `monthly`.
