# Independent V4 audit gate design and evidence

Owner: independent gate/QA worker. Ownership is limited to `scripts/v4_audit_gate.py`, `tests/test_v4_audit*.py`, and this document. No product implementation, sealed inputs, holdout, credentials, or nested agents are used.

## Baseline captured before V4 changes

Source: exact `18afaa6433284dc582d38c02b797dc4e688892f1`; initial `git status --short` was empty. Python: `/private/tmp/uptime-verify.g7EJfz/clean-venv/bin/python`. Original audit scripts were copied byte-for-byte into disposable directories and run with a sanitized environment and temporary databases. No provider requests or secret inspection occurred. Audit root: `/private/tmp/uptime-v4.WTuRU4/audit/Uptime-V3-Audit`. Relative provenance below is rooted at its `evidence/` directory. These observations are synthetic and establish implementation defects, not commercial entitlement.

Fresh browser verification is **UNAVAILABLE**: the original workflow probe reached its real socket bind and this worker sandbox denied it with `PermissionError: [Errno 1] Operation not permitted`. The original audit records successful Chromium reproduction; that archived evidence is not a fresh worker pass. The exact original nonbrowser `route_probes` and `domain_probes` were subsequently invoked without changing their code and completed. Release must fail closed until a permitted real-browser run completes.

### Original script execution receipts

```json
[
  {
    "probe": "financial/probes.py",
    "sha256": "196539928b62eca8e8e576b21d0b4d495c019bf14e88b92d1c0b61f334c5a289",
    "exit": 0,
    "stdout_sha256": "54d846d95a52c091a379624255e9a9c89b173867019da3607abe0209cb2ae1a8",
    "stderr_type": null
  },
  {
    "probe": "independent/probes.py",
    "sha256": "fcc5bb8a540496ee0ad95351ed0221fcab1fde9b266dab7e1348f342addafe13",
    "exit": 0,
    "stdout_sha256": "34b3ab799861f1e517e4502da0e85c6a9a9ff5c49cfb9da074304461a7f7ef36",
    "stderr_type": "  from starlette.testclient import TestClient as TestClient  # noqa"
  },
  {
    "probe": "independent/boundary_probes.py",
    "sha256": "7889daeb293d4f14bfe391207158917c50ab97774c5cf38f11c23b16eb9deac7",
    "exit": 0,
    "stdout_sha256": "3857f38b045b2f38afaaeb32f02c6130d2d278e32d4d855fcf771995b26aad8f",
    "stderr_type": "  from starlette.testclient import TestClient as TestClient  # noqa"
  },
  {
    "probe": "lead/lead_probes.py",
    "sha256": "d154fd0e8414f658e94b0eee07f64d3db9878230c3a0cf4639db4cd9de25a1d9",
    "exit": 0,
    "stdout_sha256": "930b59e270d54e0741d0b74b5b8749012b77e0442b5da7cfc62ed72d59fb4134",
    "stderr_type": "  from starlette.testclient import TestClient as TestClient  # noqa"
  },
  {
    "probe": "workflow/workflow_probe.py",
    "sha256": "249bd86fbb14edec56292e6729e9a97442ea3098cdebc8498f0683803f6f82d0",
    "exit": 1,
    "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_type": "PermissionError: [Errno 1] Operation not permitted"
  },
  {
    "probe": "workflow/novel_probe.py",
    "sha256": "d62b65e8865cf50db68b7e183a0241576f220e1fefd932ccb0ac9f55eb805e43",
    "exit": 0,
    "stdout_sha256": "978ec57993ba7237bb9fb59c84e9ef7e320052d61dc33020ca22597ca0d6ee53",
    "stderr_type": "  from starlette.testclient import TestClient as TestClient  # noqa"
  }
]
```

### Observed financial counterexamples

| Audit probe ID | Observed at exact V3 | Independent audit expectation | Kind |
|---|---|---|---|
| P-fold-incorrect-version | `["ELIGIBLE", "5.00", ["amendment-v2"]]` | `["INELIGIBLE", "0.00", ["agreement-v1"]]` | defect |
| P-fold-conflicting-provider-date | `"accepted"` | `"rejected"` | defect |
| T-distant-out-of-period-unknown | `["INSUFFICIENT_EVIDENCE", null]` | `["ELIGIBLE", "100.0000"]` | defect |
| T-padded-repeat | `["ELIGIBLE", "200.0000"]` | `["INSUFFICIENT_EVIDENCE", null]` | defect |
| D-cent-claim-drops-to-zero | `["INELIGIBLE", null]` | `["ELIGIBLE", "0.0010"]` | defect |
| D-predates-governing-SLA | `["ELIGIBLE", "100.00"]` | `["UNSUPPORTED_RULE", null]` | defect |
| D-missing-doc-reference | `["ELIGIBLE", "100.00"]` | `["INSUFFICIENT_EVIDENCE", null]` | defect |
| D-missing-ref-at-ticket-construction | `"KeyError 'ref'"` | `"blocked prior to approval"` | defect |
| J-ambient-rounding-alters-tier | `["INELIGIBLE", null]` | `["ELIGIBLE", "120.00"]` | defect |
| B-padded-repeat-triggers-tier | `["ELIGIBLE", "2000.00"]` | `["INSUFFICIENT_EVIDENCE", null]` | defect |
| T-blank-document-provenance | `["ELIGIBLE", "100.0000"]` | `["INSUFFICIENT_EVIDENCE", null]` | defect |
| R-multi-award-same-bill-total | `"160.00"` | `"at most 100.00 or explicit scope error"` | design gap |
| R-zero-cent-partial-stage | `["PARTIALLY_APPLIED", "0.00", 1]` | `["POSTED", "0.00", 0]` | defect |
| R-different-product-account-before-award | `"80.00"` | `"reject or report insufficient scope evidence"` | design gap |
| D-desk-old-terms-can-approve | `"CLAIM_APPROVED"` | `"no approval action"` | defect |
| J-issuance-vs-filing | `"INELIGIBLE"` | `"timely filing retained, issuance blocked/undetermined"` | design gap |

### Observed workflow and comparative API counterexamples

Provenance: `workflow/nonbrowser.observed.json`; stdout SHA-256 `c6ed77fc0e0a94330797578c4b20e0e25693e8c2773bb38815cbc1291b152d62`.

```json
{
  "stock_denial": {
    "prefiling_outcome": "ELIGIBLE",
    "prefiling_amount": "100.00",
    "prefiling_evidence": [
      "Customer invoice lines",
      "Customer invoice lines",
      "Customer invoice lines",
      "Customer invoice lines",
      "status_summary",
      "component_record"
    ],
    "terminal_stage": "DENIAL_ACCEPTED",
    "receipts": 1,
    "claimed": "100.00",
    "awarded": "0.00",
    "postfiling_evidence": [
      "Customer invoice lines",
      "Customer invoice lines",
      "Customer invoice lines",
      "Customer invoice lines",
      "status_summary",
      "component_record",
      "Customer copy of maintenance notice"
    ]
  },
  "local_activation": {
    "states": [
      "SHADOW",
      "ACTIVE",
      "REVOKED"
    ],
    "amounts": [
      "120.00",
      "120.00",
      "120.00"
    ],
    "case_counts": [
      16,
      16
    ],
    "same_cases": true,
    "reactivation_actions": [],
    "viewer_post": 403,
    "foreign_session_post": 403
  },
  "action_aba": {
    "B_old_approval_status": 409,
    "B_all_checks_passed": true,
    "rollback_to_A_state": "SHADOW",
    "original_pre_revoke_approve_status": 200,
    "original_pre_revoke_activate_status": 200,
    "final_state": "ACTIVE"
  },
  "source_bytes_only": {
    "http_status": 200,
    "state": "ACTIVE",
    "version_unchanged": true
  },
  "source_raw_result": {
    "http_status": 200,
    "state": "ACTIVE",
    "version_unchanged": true
  },
  "source_malformed_type": {
    "http_status": 200,
    "state": "DRAFT",
    "version_unchanged": false
  },
  "source_unparseable": {
    "error_status": 409,
    "after_restore_state": "ACTIVE",
    "audit_events_added": 0
  },
  "complete_only_policy": {
    "policy_scope": "One separately approved, complete initial simulator claim only. No real outward communications.",
    "stage_after_approval": "NEEDS_EVIDENCE",
    "submitted_refs": [
      "status-1-summary"
    ],
    "simulator_response": "DOCUMENTATION_NEEDED",
    "requested_kind": "component_record"
  },
  "cross_mode_same_db": {
    "old_session_GET": 200,
    "new_mode": "sandbox",
    "reported_policy": "POLICY_AUTOMATED",
    "available_modes": [
      "OBSERVE",
      "ASSISTED"
    ],
    "old_session_POST": 200,
    "approved_by": "scripted-test-reviewer",
    "auto_dispatched": 0
  },
  "direct_counterparty_account_binding": {
    "bears": [
      "AWARD",
      "100.00"
    ],
    "other-tenant": [
      "AWARD",
      "100.00"
    ]
  }
}
```

Provenance: `workflow/novel_probe.observed.json`; stdout SHA-256 `978ec57993ba7237bb9fb59c84e9ef7e320052d61dc33020ca22597ca0d6ee53`.

```json
{
  "dispute-novel-positive": {
    "stages": [
      "CLAIM_APPROVED",
      "NEEDS_EVIDENCE",
      "RESPONSE_DRAFTED",
      "RESPONSE_APPROVED",
      "RESPONSE_APPROVED",
      "AWARDED"
    ],
    "filing_preflight": "ELIGIBLE",
    "receipt_count": 2,
    "award": "41.73",
    "responses": [
      "DOCUMENTATION_NEEDED",
      "AWARD"
    ]
  },
  "dispute-novel-missing-component": {
    "stages": [
      "CLAIM_APPROVED",
      "NEEDS_EVIDENCE",
      "RESPONSE_DRAFTED",
      "RESPONSE_APPROVED",
      "RESPONSE_APPROVED",
      "AWARDED"
    ],
    "filing_preflight": "ELIGIBLE",
    "receipt_count": 2,
    "award": "41.73",
    "responses": [
      "DOCUMENTATION_NEEDED",
      "AWARD"
    ]
  },
  "dispute-novel-wrong-line-scope": {
    "stages": [
      "CLAIM_APPROVED",
      "NEEDS_EVIDENCE",
      "RESPONSE_DRAFTED",
      "RESPONSE_APPROVED",
      "RESPONSE_APPROVED",
      "AWARDED"
    ],
    "filing_preflight": "ELIGIBLE",
    "receipt_count": 2,
    "award": "41.73",
    "responses": [
      "DOCUMENTATION_NEEDED",
      "AWARD"
    ]
  }
}
```

Provenance: `independent/boundary_probes.observed.json`; stdout SHA-256 `3857f38b045b2f38afaaeb32f02c6130d2d278e32d4d855fcf771995b26aad8f`.

```json
{
  "duplicate_business_obligation": [
    {
      "case": "dispute-partial",
      "digest": "800888454b8137b40c0979621342b9c68853fff4cc0a802a89330743c595d7c1",
      "idempotency_key": "8949e7bc8c2ac8c2981ecab2bce7bc0746ae7ed358277b287a319fe39352d72b",
      "claimed": "100.00",
      "awarded": "80.00"
    },
    {
      "case": "dispute-clone",
      "digest": "800888454b8137b40c0979621342b9c68853fff4cc0a802a89330743c595d7c1",
      "idempotency_key": "d4998bfe976b40f01bb3dc9b9ca20b6491556b6dbe37a0c66beea5df8313d3a1",
      "claimed": "100.00",
      "awarded": "80.00"
    }
  ],
  "privacy_minimization": {
    "class_label": "redacted_replay",
    "sentinel_reached_local_simulator": [
      true
    ],
    "result": "HUMAN_REVIEW",
    "reply": "UNVERIFIED_DOCUMENT"
  }
}
```

Provenance: `independent/probes.observed.json`; stdout SHA-256 `34b3ab799861f1e517e4502da0e85c6a9a9ff5c49cfb9da074304461a7f7ef36`.

```json
{
  "known_exclusion": {
    "archived_before_start_hours": 26.0,
    "initial": "ELIGIBLE",
    "offered": [
      {
        "id": "approve-claim",
        "label": "Approve simulated claim"
      }
    ],
    "after_submit": "DENIAL_ACCEPTED",
    "simulated_claim": "100.00",
    "initial_evidence_names": [
      "Customer invoice lines",
      "Customer invoice lines",
      "Customer invoice lines",
      "Customer invoice lines",
      "status_summary",
      "component_record"
    ]
  },
  "incoming_WINDOW_CLOSED": {
    "stage": "EXPIRED",
    "outcome": "INELIGIBLE",
    "at": "2026-11-02T10:01:00+00:00",
    "deadline_exclusive": "2026-12-01T00:00:00+00:00",
    "awarded": "0.00"
  },
  "incoming_FREEFORM_MISSING_DOC": {
    "stage": "HUMAN_REVIEW",
    "outcome": "INSUFFICIENT_EVIDENCE",
    "at": "2026-11-02T10:01:00+00:00",
    "deadline_exclusive": "2026-12-01T00:00:00+00:00",
    "awarded": "0.00"
  },
  "active_lab": {
    "state": "ACTIVE",
    "active": true,
    "dashboard_case_ids_unchanged": true,
    "atlassian_dashboard_case_count": 0
  },
  "novel_vendor": "Unsupported operation or product scope",
  "zero_fee_jira": {
    "outcome": "ELIGIBLE",
    "amount": "0.00"
  },
  "fold_pricing": [
    {
      "utc_service": [
        "2026-11-01T08:45:00+00:00",
        "2026-11-01T08:55:00+00:00"
      ],
      "utc_amendment": "2026-11-01T09:30:00+00:00",
      "outcome": "ELIGIBLE",
      "overcharge": "7500.00",
      "version": "amendment-v2"
    },
    {
      "utc_service": [
        "2026-11-01T08:45:00+00:00",
        "2026-11-01T08:55:00+00:00"
      ],
      "utc_amendment": "2026-11-01T09:30:00+00:00",
      "outcome": "INELIGIBLE",
      "overcharge": "0.00",
      "version": "agreement-v1"
    }
  ],
  "old_unrelated_twilio_interval": {
    "baseline": {
      "outcome": "ELIGIBLE",
      "amount": "100.0000"
    },
    "with_unverified_unrelated_interval": {
      "outcome": "INSUFFICIENT_EVIDENCE",
      "amount": null
    }
  },
  "unrelated_outside_invoice_line": {
    "with_excluded_service": {
      "outcome": "INELIGIBLE",
      "amount": null
    },
    "overcharge": "None",
    "last_trace": "FAIL CLOSED: Line support: outside agreement performance period",
    "same_covered_line_alone": {
      "outcome": "ELIGIBLE",
      "amount": "7500.00"
    }
  },
  "contradictory_line_metadata": {
    "outcome": "ELIGIBLE",
    "amount": "100.00"
  }
}
```

Provenance: `lead/lead_probes.observed.json`; stdout SHA-256 `930b59e270d54e0741d0b74b5b8749012b77e0442b5da7cfc62ed72d59fb4134`.

```json
{
  "captured_line_has_units_but_view_calls_them_missing": {
    "input": {
      "id": "line",
      "amount": {
        "amount": "37500.00",
        "currency": "USD"
      },
      "quantity": "1000",
      "unit_price": {
        "amount": "37.50",
        "currency": "USD"
      },
      "service_date": "2026-10-01",
      "sku": "verified-example"
    },
    "outcome": "INSUFFICIENT_EVIDENCE",
    "trace": [
      "No verified negotiated terms or allocation bind this bill to a customer contract.",
      "Missing: verified governing agreement, performance date, service mapping, units and unit price. The bill total cannot establish an overcharge."
    ]
  },
  "nullable_status_malformed_capture_http": 500,
  "paid_case_selected_as_unpaid": {
    "stage": "RETROSPECTIVE_REVIEW",
    "metric": {
      "label": "Invoice exposure",
      "value": "$9,123.45",
      "note": "One unpaid synthetic invoice; amendment-aware discrepancy before approval.",
      "sources": [
        "SYNTHETIC_CUSTOMER",
        "DETERMINISTIC_REPLAY"
      ],
      "case_id": "price-000-audit"
    }
  },
  "reimport_same_case_silently_preserves_old": {
    "new": "17.00",
    "served": "9123.45"
  },
  "viewer_change_policy_http": 403,
  "unseen_document_intake_http": 404,
  "novel_vendor_reply_http": 404,
  "unseen_service_compile": "Unsupported operation or product scope",
  "guide_wrong_intent": {
    "Show my billing profile.": "next",
    "Show the support evidence.": "proof"
  },
  "guide_limit": {
    "ui_max_length": 2000,
    "api_status_for_1001": 422
  },
  "isolated_awards_same_bill": {
    "bill": "100.00",
    "applied_per_call": [
      "80.00",
      "80.00"
    ]
  }
}
```

## Release gate contract and consequential tradeoffs for lead review

The expected outcomes come from independent audit assertions and the stated invariants, never from V4 implementation output. Every required check must execute; missing interfaces, runtime errors, unavailable browsers and unrun groups block release. Explicit V3 known limits remain a distinct category and cannot be counted as fixed defects. A separate before/after report preserves source hashes, callable IDs, expected results and observed outcomes. Reports contain synthetic summaries only, never session tokens, arbitrary exception messages, or raw provider records.

The lead has been asked for the V4 authentication/bootstrap protocol and changed input/reconciliation interfaces. Adapters may change setup and response extraction only; negative assertions and financial expectations remain independent.

**Tradeoffs needing central review:** (1) global B08 allocation requires a durable portfolio interface: isolated award calls cannot establish safety; (2) B01 requires a real browser and sibling loopback service, so TestClient checks cannot substitute; (3) Jira good-standing at issuance versus timely filing is an audit design gap whose final staged schema needs a lead-reviewed contract; (4) sub-cent contractual estimates must remain distinct from settlement rounding, since the audit established no provider rounding rule. The worker does not interpret these as commercial authority or resolve them by changing product behavior.

## Executable gate handoff (commit 227e976)

`scripts/v4_audit_gate.py` always executes the independent probe callables. It does not accept uploaded pass counts, infer missing coverage, skip unavailable groups, or use candidate output as gold. Every result identifies its callable and exact original audit source hash. `synthetic_input_sha256` identifies the actual synthetic input files; the gate does not read the separate sealed holdout. Code hashes identify the runner and probe modules.

The baseline phase creates a fresh `git archive` of **18afaa6433284dc582d38c02b797dc4e688892f1**, regardless of the current branch head. The release phase uses the requested checkout and compares against an explicit baseline report. A missing baseline, changed expected outcome, missing/duplicate check, unavailable validator, or browser execution gap prevents `release_pass`. No report generated in baseline mode can certify release.

```sh
PY=/private/tmp/uptime-verify.g7EJfz/clean-venv/bin/python
$PY scripts/v4_audit_gate.py --phase baseline --report /private/tmp/uptime-v3-before.json
$PY scripts/v4_audit_gate.py --phase release --source . \
  --before /private/tmp/uptime-v3-before.json --report /private/tmp/uptime-v4-after.json
```

Exit codes: baseline `0` means all required probes/validators executed, not that V3 satisfies the release assertions; baseline `2` means required verification is unavailable. Release `0` alone means the complete release gate passed, and release `1` means it did not. A nonzero baseline is deliberately preserved here.

### Actual verification and limitations

The complete suite ran through the shared installed environment with `UV_CACHE_DIR=/private/tmp/uptime-v4.WTuRU4/generalqa-uv-cache UV_PROJECT_ENVIRONMENT=/private/tmp/uptime-v4.WTuRU4/venv uv run --locked --no-sync pytest -q`: **634 passed**, one existing Starlette/httpx deprecation warning, 21.99 seconds. This is the existing 475 cases plus 159 gate tests; parameterized omission tests are not independent product bug discoveries. `--no-sync` avoids mutating the lead's shared Hypothesis-enabled environment. The first plain uv invocation was denied access to the default cache; the temporary cache resolved that issue. No merge was performed by this worker; the lead must run the mandated `uv run --locked pytest` after integration.

The gate tests execute real immutable V3 code, reproduce frozen independent counterexamples, retain positive controls, exercise maliciously missing/duplicate evidence and false pass flags, test baseline assertion drift, and verify that exception messages cannot disclose values in reports. Passing these tests proves gate behavior, **not** V4 correctness.

Both final CLI invocations used the original clean audit interpreter. The before run exited `2`; the after run against still-unchanged V3 product code exited `1`. Each has **74 passing observations, 35 failed release assertions and 5 unavailable validations**. These are observation counts, not 114 independent bugs. The result remains `release_pass: false`.

The five unavailable validations are explicit:

- `W-browser-sibling-origin`: real loopback socket bind denied by this worker sandbox. Archived successful browser attack evidence remains distinct from a fresh run.
- `A-ui-financial-join-ids`: same real-browser runtime is unavailable; it must display the receipt, credit, bill and application identifiers from an actually completed UI reconciliation.
- `R-multi-award-same-bill-total`: exact V3 observed $160 applied across two awards against one $100 bill; a durable global allocation interface must be supplied before a meaningful V4 validator can bind to it.
- `R-different-product-account-before-award`: exact V3 observed $80 applied despite contradictory product/account/period metadata; the reviewed restriction schema is pending.
- `J-issuance-vs-filing`: exact V3 reports INELIGIBLE; a reviewed interface must distinguish timely filing from issuance eligibility. The audit's prose expected outcome is not misrepresented as an executable staged-state predicate.

The V4 auth/bootstrap and changed input protocols remain requested and unavailable at this handoff. `tasks/V4-REQUEST.txt` has not been staged in this appointed worktree. `bootstrap`, fixture provisioning and extraction of staged results are the intended adapter seams; assertions must remain independent. Until those schemas arrive, successful V3 auth setup does not establish V4 auth compatibility. All resulting setup failures remain UNAVAILABLE.

### Required primary coverage

| Primary audit defect | Required callable observation IDs |
|---|---|
| B01 | `W-browser-sibling-origin`, `W-mode-session-isolation` |
| B02 | `W-known-exclusion-before-filing`, `W-complete-policy-packet` |
| B03 | `D-predates-governing-SLA`, `D-desk-old-terms-can-approve`, `W-novel-missing-component`, `W-novel-wrong-line-scope`, `W-reply-WINDOW_CLOSED` |
| B04 | `P-fold-incorrect-version`, `P-fold-conflicting-provider-date`, `P-unrelated-outside-line` |
| B05 | `T-padded-repeat`, `B-padded-repeat-triggers-tier` |
| B06 | `W-business-claim-idempotency`, `W-outbound-allowlist` |
| B07 | `W-lifecycle-ABA`, `W-malformed-source-quarantine` |
| B08 | `R-multi-award-same-bill-total`, `R-zero-cent-partial-stage`, `R-different-product-account-before-award` |

### Durable final before/after evidence

Before: `/private/tmp/uptime-v4.WTuRU4/generalqa-baseline/gate-baseline-final.json`; SHA-256 `25cdc9dd632feea2d14003a7cca971d6590b9170fbcbf32a0c87606a79c40df5`; generated `2026-11-04T22:34:38.239051+00:00`; source `18afaa6433284dc582d38c02b797dc4e688892f1`.

After: `/private/tmp/uptime-v4.WTuRU4/generalqa-baseline/gate-release-final.json`; SHA-256 `d7a7fab2dcfbbaa12a53c4761efd9cb9e45109d81bc84c129ed0b154f754b686`; generated `2026-11-04T22:34:40.693228+00:00`; source `227e97618a8463e2656bcca741dd653f62afd092`.

Full report code and input provenance:

```json
{
  "gate_code": {
    "scripts/v4_audit_gate.py": "7c7baa1f58836098ae9403ffde301de5c042c958dced1f54790c4ee45a0c1dce",
    "tests/test_v4_audit_browser.py": "e89fcaec83e44eb51ed374a23247b59c54aec6d224be29c8c8dbd0d9a3bb77e1",
    "tests/test_v4_audit_financial.py": "6c948dd5224f71218a0e0727e6f80db198f44ff89cff9c14b2c215af403b2a05",
    "tests/test_v4_audit_gate.py": "22e490ea425657cafc97dc639e974e54a5f02cb3ed29e555e69abbdc50fd74eb",
    "tests/test_v4_audit_workflow.py": "dd7511ff87fb3b993ea687f61be0719140dd8e032019e1b3227a52bcc5d635b2"
  },
  "synthetic_input_sha256": {
    "fixtures/disputes/claimant/dossiers.json": "5678c145ecd321b226ca2e1e4837c50406c2a24f4fb0eeac85a086d7ddf665e5",
    "fixtures/disputes/simulator/records.json": "ff2c59c5ca4fb05f1559fa463ab05e5090096d490fa71538774360a2cac0859d",
    "fixtures/onboarding/extraction.json": "2bdd9d3740de9f349f4e8046957c659ff45f51a53533eed6c3d232aad4ac04b7",
    "fixtures/onboarding/overlay.json": "ea630cfe2779d60c03ef04c799e1477401d47d6a0e3ef76d365b6a36f7bf7714",
    "fixtures/onboarding/observations.json": "1b67a7ca79e3dd8d1dc75d649df9548812ebdceb0b0590d4b775e04ad570610c",
    "fixtures/pricing/agreement.json": "797e3240283f50c7d1c23c90a1d2fe73e13efae6eb3c6330ae99b673714f0123",
    "fixtures/pricing/cases.json": "13675a64789fa7100cb20b18c236423620edcc13197945e71dab2c9891acc0cb",
    "fixtures/twilio/cases.json": "fe99f6e08ffd5fa0c50d44307a2493504f6f1ee6e1de6f56cd8d39d42069d175",
    "fixtures/other_obligations/agreement.txt": "62ebae7fa9d8e079ff0b032c2862f79ac0a5c9baab045483af0bf59777903452",
    "fixtures/other_obligations/examples.json": "06ac26b235d7b2f2d41b82b7b9512ea791eaa1b2695fcb06724bb59ca7c22f56"
  }
}
```

The following compact copy makes every observation durable even after temporary JSON files disappear. Before and after observations/statuses are identical because no V4 product changes were present in this worktree. `v3-known-limit` distinguishes intentionally unsupported coverage; `design gap` remains a blocked interface requirement, not a claimed repair.

| Observation | Category | Before / after | Observed | Independent expected / pending validator |
|---|---|---|---|---|
| `P-UTC-control` | control | PASS / PASS | `["INELIGIBLE", "0.00", ["agreement-v1"]]` | `["INELIGIBLE", "0.00", ["agreement-v1"]]` |
| `P-fold-incorrect-version` | defect | FAIL / FAIL | `["ELIGIBLE", "5.00", ["amendment-v2"]]` | `["INELIGIBLE", "0.00", ["agreement-v1"]]` |
| `P-fold-conflicting-provider-date` | defect | FAIL / FAIL | `"accepted"` | `"rejected"` |
| `T-proven-month` | control | PASS / PASS | `["ELIGIBLE", "100.0000"]` | `["ELIGIBLE", "100.0000"]` |
| `T-distant-out-of-period-unknown` | defect | FAIL / FAIL | `["INSUFFICIENT_EVIDENCE", null]` | `["ELIGIBLE", "100.0000"]` |
| `T-padded-repeat` | defect | FAIL / FAIL | `["ELIGIBLE", "200.0000"]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `T-exact-repeat` | control | PASS / PASS | `["INSUFFICIENT_EVIDENCE", null]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `D-known-ordinary-case` | control | PASS / PASS | `["ELIGIBLE", "100.00"]` | `["ELIGIBLE", "100.00"]` |
| `D-cent-positive-W2` | control | PASS / PASS | `["ELIGIBLE", "0.0010"]` | `["ELIGIBLE", "0.0010"]` |
| `D-cent-claim-drops-to-zero` | defect | FAIL / FAIL | `["INELIGIBLE", null]` | `["ELIGIBLE", "0.0010"]` |
| `D-predates-governing-SLA` | defect | FAIL / FAIL | `["ELIGIBLE", "100.00"]` | `["UNSUPPORTED_RULE", null]` |
| `T-historical-version-control` | control | PASS / PASS | `["UNSUPPORTED_RULE", null]` | `["UNSUPPORTED_RULE", null]` |
| `D-missing-doc-reference` | defect | FAIL / FAIL | `["ELIGIBLE", "100.00"]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `D-missing-ref-at-ticket-construction` | defect | FAIL / FAIL | `"KeyError 'ref'"` | `"blocked prior to approval"` |
| `T-last-instant` | control | PASS / PASS | `["ELIGIBLE", "100.0000"]` | `["ELIGIBLE", "100.0000"]` |
| `T-first-late-instant` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `T-prior-receipt` | control | PASS / PASS | `["ELIGIBLE", "100.0000"]` | `["ELIGIBLE", "100.0000"]` |
| `T-no-attribution` | control | PASS / PASS | `["INSUFFICIENT_EVIDENCE", null]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `T-incomplete-status-month` | control | PASS / PASS | `["INSUFFICIENT_EVIDENCE", null]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `T-tax-carrier-third-party` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `T-partial-coverage` | control | PASS / PASS | `["INSUFFICIENT_EVIDENCE", null]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `T-connection-throughput` | v3-known-limit | PASS / PASS | `["UNSUPPORTED_RULE", null]` | `["UNSUPPORTED_RULE", null]` |
| `T-base-boundary-at` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `T-base-boundary-above` | control | PASS / PASS | `["ELIGIBLE", "100.0000"]` | `["ELIGIBLE", "100.0000"]` |
| `T-min-5-exact` | control | PASS / PASS | `["ELIGIBLE", "100.0000"]` | `["ELIGIBLE", "100.0000"]` |
| `T-min-below-5` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `T-admin-before-cutoff` | control | PASS / PASS | `["ELIGIBLE", "100.0000"]` | `["ELIGIBLE", "100.0000"]` |
| `T-admin-cutoff` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `T-exclusion-splits-short-spans` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `T-short-notice` | control | PASS / PASS | `["ELIGIBLE", "100.0000"]` | `["ELIGIBLE", "100.0000"]` |
| `T-across-month-five-before-clipping` | control | PASS / PASS | `["ELIGIBLE", "100.0000"]` | `["ELIGIBLE", "100.0000"]` |
| `T-across-month-fraction-under-five` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `J-positive` | control | PASS / PASS | `["ELIGIBLE", "120.00"]` | `["ELIGIBLE", "120.00"]` |
| `J-explicit-vendor-aggregate` | control | PASS / PASS | `["INSUFFICIENT_EVIDENCE", null]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `J-threshold-operator` | control | PASS / PASS | `["INSUFFICIENT_EVIDENCE", null]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `J-june-43min-premium` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `J-june-44min-premium` | control | PASS / PASS | `["ELIGIBLE", "120.00"]` | `["ELIGIBLE", "120.00"]` |
| `J-june-22min-enterprise` | control | PASS / PASS | `["ELIGIBLE", "60.00"]` | `["ELIGIBLE", "60.00"]` |
| `J-june-21min-enterprise` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `J-99-exact` | control | PASS / PASS | `["ELIGIBLE", "120.00"]` | `["ELIGIBLE", "120.00"]` |
| `J-99-below` | control | PASS / PASS | `["ELIGIBLE", "300.00"]` | `["ELIGIBLE", "300.00"]` |
| `J-95-exact` | control | PASS / PASS | `["ELIGIBLE", "300.00"]` | `["ELIGIBLE", "300.00"]` |
| `J-95-below` | control | PASS / PASS | `["ELIGIBLE", "600.00"]` | `["ELIGIBLE", "600.00"]` |
| `J-on-time` | control | PASS / PASS | `["ELIGIBLE", "120.00"]` | `["ELIGIBLE", "120.00"]` |
| `J-late` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `J-sandbox` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `J-general-surface` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `J-other-product` | v3-known-limit | PASS / PASS | `["UNSUPPORTED_RULE", null]` | `["UNSUPPORTED_RULE", null]` |
| `J-reseller` | v3-known-limit | PASS / PASS | `["UNSUPPORTED_RULE", null]` | `["UNSUPPORTED_RULE", null]` |
| `J-technical-ticket` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `J-good-standing` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `J-challenge-local-holiday` | control | PASS / PASS | `"2026-07-09"` | `"2026-07-09"` |
| `J-unknown-holiday-list` | control | PASS / PASS | `null` | `null` |
| `J-ambient-rounding-alters-tier` | defect | FAIL / FAIL | `["INELIGIBLE", null]` | `["ELIGIBLE", "120.00"]` |
| `B-single-below-threshold` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `B-identical-repeat` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `B-padded-repeat-triggers-tier` | defect | FAIL / FAIL | `["ELIGIBLE", "2000.00"]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `B-inclusive-and-earlier-credit` | control | PASS / PASS | `["ELIGIBLE", "1750.00"]` | `["ELIGIBLE", "1750.00"]` |
| `B-inclusive-minus-one-cent` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `B-only-closed-year` | control | PASS / PASS | `["INSUFFICIENT_EVIDENCE", null]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `B-cross-currency` | v3-known-limit | PASS / PASS | `["UNSUPPORTED_RULE", null]` | `["UNSUPPORTED_RULE", null]` |
| `T-blank-document-provenance` | defect | FAIL / FAIL | `["ELIGIBLE", "100.0000"]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `T-no-document-provenance` | control | PASS / PASS | `["INSUFFICIENT_EVIDENCE", null]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `R-idempotent-positive` | control | PASS / PASS | `["80.00", "80.00", "80.00", null]` | `["80.00", "80.00", "80.00", null]` |
| `R-multi-award-same-bill-total` | design gap | UNAVAILABLE / UNAVAILABLE | `"160.00"` | `"durable cross-award allocation interface"` |
| `R-single-award-bill-cap` | control | PASS / PASS | `"rejected"` | `"rejected"` |
| `R-zero-cent-partial-stage` | defect | FAIL / FAIL | `["PARTIALLY_APPLIED", "0.00", 1]` | `["POSTED", "0.00", 0]` |
| `R-different-product-account-before-award` | design gap | UNAVAILABLE / UNAVAILABLE | `"80.00"` | `"award restriction and bill scope interface"` |
| `P-tier-999` | control | PASS / PASS | `["INELIGIBLE", "0.00", ["amendment-v2"]]` | `["INELIGIBLE", "0.00", ["amendment-v2"]]` |
| `P-tier-1000` | control | PASS / PASS | `["INELIGIBLE", "0.00", ["amendment-v2"]]` | `["INELIGIBLE", "0.00", ["amendment-v2"]]` |
| `P-tier-1001` | control | PASS / PASS | `["INELIGIBLE", "0.00", ["amendment-v2"]]` | `["INELIGIBLE", "0.00", ["amendment-v2"]]` |
| `P-amendment-end` | control | PASS / PASS | `["INELIGIBLE", "0.00", ["agreement-v1"]]` | `["INELIGIBLE", "0.00", ["agreement-v1"]]` |
| `P-amendment-start` | control | PASS / PASS | `["INELIGIBLE", "0.00", ["amendment-v2"]]` | `["INELIGIBLE", "0.00", ["amendment-v2"]]` |
| `P-unsplit-amendment` | v3-known-limit | PASS / PASS | `["INSUFFICIENT_EVIDENCE", "None", []]` | `["INSUFFICIENT_EVIDENCE", "None", []]` |
| `P-unimplemented-mode` | v3-known-limit | PASS / PASS | `["UNSUPPORTED_RULE", "None", []]` | `["UNSUPPORTED_RULE", "None", []]` |
| `P-unimplemented-quantity_scope` | v3-known-limit | PASS / PASS | `["UNSUPPORTED_RULE", "None", []]` | `["UNSUPPORTED_RULE", "None", []]` |
| `P-late-amendment` | v3-known-limit | PASS / PASS | `["UNSUPPORTED_RULE", "None", []]` | `["UNSUPPORTED_RULE", "None", []]` |
| `D-desk-old-terms-can-approve` | defect | FAIL / FAIL | `"CLAIM_APPROVED"` | `"no approval action"` |
| `J-issuance-vs-filing` | design gap | UNAVAILABLE / UNAVAILABLE | `"INELIGIBLE"` | `"separate filing and issuance result interface"` |
| `T-enhanced-SendGrid-region-is-not-availability-input` | control | PASS / PASS | `["ELIGIBLE", "100.0000"]` | `["ELIGIBLE", "100.0000"]` |
| `T-base-SendGrid-at-same-duration` | control | PASS / PASS | `["INELIGIBLE", null]` | `["INELIGIBLE", null]` |
| `T-enhanced-SendGrid-independent-remedy` | v3-known-limit | PASS / PASS | `["UNSUPPORTED_RULE", null]` | `["UNSUPPORTED_RULE", null]` |
| `T-foreign-status-host` | control | PASS / PASS | `["INSUFFICIENT_EVIDENCE", null]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `T-region-scope-dispute-preflight` | control | PASS / PASS | `["INSUFFICIENT_EVIDENCE", null]` | `["INSUFFICIENT_EVIDENCE", null]` |
| `T-500-overlap-gap-cross-boundary-patterns` | control | PASS / PASS | `[]` | `[]` |
| `W-known-exclusion-before-filing` | defect | FAIL / FAIL | `{"outcome": "ELIGIBLE", "approval_offered": true, "approval_denied": false, "receipts": 0}` | `{"outcome": "INELIGIBLE", "approval_offered": false, "approval_denied": true, "receipts": 0}` |
| `W-complete-policy-packet` | defect | FAIL / FAIL | `{"missing_component_reply": true, "policy_claims_complete": true}` | `{"missing_component_reply": false, "policy_claims_complete": true}` |
| `W-reply-WINDOW_CLOSED` | defect | FAIL / FAIL | `{"stage": "EXPIRED", "awarded": "0.00", "has_receipt": true}` | `{"stage": "HUMAN_REVIEW", "awarded": "0.00", "has_receipt": true}` |
| `W-reply-FREEFORM_MISSING_DOC` | control | PASS / PASS | `{"stage": "HUMAN_REVIEW", "awarded": "0.00", "has_receipt": true}` | `{"stage": "HUMAN_REVIEW", "awarded": "0.00", "has_receipt": true}` |
| `W-business-claim-idempotency` | defect | FAIL / FAIL | `2` | `1` |
| `W-outbound-allowlist` | defect | FAIL / FAIL | `true` | `false` |
| `W-lifecycle-ABA` | defect | FAIL / FAIL | `[409, 200, 200]` | `[409, 409, 409]` |
| `W-malformed-source-quarantine` | defect | FAIL / FAIL | `{"request_rejected_or_quarantined": true, "silently_active": true, "audit_added": false}` | `{"request_rejected_or_quarantined": true, "silently_active": false, "audit_added": true}` |
| `W-viewer-boundary` | control | PASS / PASS | `403` | `403` |
| `W-mode-session-isolation` | defect | FAIL / FAIL | `false` | `true` |
| `W-mode-policy-isolation` | defect | FAIL / FAIL | `false` | `true` |
| `W-novel-positive` | control | PASS / PASS | `"41.73"` | `"41.73"` |
| `W-novel-missing-component` | defect | FAIL / FAIL | `"41.73"` | `"0.00"` |
| `W-novel-wrong-line-scope` | defect | FAIL / FAIL | `{"receipts": 2, "awarded": "41.73", "eligible": true}` | `{"receipts": 0, "awarded": "0.00", "eligible": false}` |
| `W-tenant-account-positive` | control | PASS / PASS | `["AWARD", "100.00"]` | `["AWARD", "100.00"]` |
| `W-tenant-account-binding` | defect | FAIL / FAIL | `true` | `false` |
| `A-prevention-paid-title` | defect | FAIL / FAIL | `["price-000-audit", "$9,123.45"]` | `["price-prepayment", "$7,500.00"]` |
| `A-case-revision-not-silent` | defect | FAIL / FAIL | `false` | `true` |
| `A-billing-profile-intent` | defect | FAIL / FAIL | `true` | `false` |
| `A-guide-ui-api-limit` | defect | FAIL / FAIL | `422` | `200` |
| `A-provider-line-preserves-known-facts` | defect | FAIL / FAIL | `true` | `false` |
| `A-null-bill-status-resilience` | defect | FAIL / FAIL | `false` | `true` |
| `W-activation-runtime` | v3-known-limit | FAIL / FAIL | `{"adds_governed_case": false, "rollback_removes_active_case": false}` | `{"adds_governed_case": true, "rollback_removes_active_case": true}` |
| `P-covered-line-positive` | control | PASS / PASS | `"7500.00"` | `"7500.00"` |
| `P-unrelated-outside-line` | defect | FAIL / FAIL | `"None"` | `"7500.00"` |
| `J-zero-fee-not-claimable` | defect | FAIL / FAIL | `true` | `false` |
| `A-unattested-capture-provenance` | defect | FAIL / FAIL | `false` | `true` |
| `W-browser-sibling-origin` | required | UNAVAILABLE / UNAVAILABLE | `"PermissionError"` | `"PermissionError"` |
| `A-ui-financial-join-ids` | required | UNAVAILABLE / UNAVAILABLE | `"PermissionError"` | `"PermissionError"` |
