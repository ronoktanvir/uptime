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
