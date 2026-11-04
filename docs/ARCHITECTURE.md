# Runtime architecture

A single local FastAPI process serves the browser workbench, typed contract results, and transactional workflow state. The browser displays server results and requests allowed actions. A database session fixes the workspace, principal and role. None of the public HTTP action endpoints accepts a client-supplied tenant, eligible amount, vendor receipt or provider authorization.

```text
Public SLA / status           synthetic agreement / invoice       Ramp sandbox
      │                                  │                            │
 pinned source + model proposal     signed fixture + dates        scoped reads
      │                                  │                            │
 declarative candidate + gold       Twilio and pricing rules     sanitized IDs
      └───────── cited evidence / deterministic outcomes ─────────────┘
                              │
                    case snapshots and timeline
                              │
        reviewer / approved policy → independent simulator → denial / award
                              │
                 confirmed memo → credit record → bill application
                              │
                      read-only contextual guide
```

## Truth and accounting

`uptime/contracts.py` defines source labels, citations, four eligibility outcomes and Decimal-based USD claim amounts. Domain inputs use typed vendor-specific extensions. The Twilio engine merges qualified intervals and checks dated terms, plan, exclusions, claim evidence, eligible monthly fees and filing window. Its SendGrid throughput branch deliberately returns unsupported. A pricing agreement has temporal versions, explicit tier semantics, signatories, service mapping and immutable performance allocations. Incomplete mappings suppress the aggregate. Provider bill totals remain native-currency observations even when the evaluator cannot support that currency.

`uptime/workbench.py` projects the prevention example and a single canonical dispute separately. Alternate scenarios test refusals, missing evidence and ambiguity. The dashboard never adds alternatives into one ROI figure. `uptime/reconciliation.py` validates vendor, tenant, currency, memo, credit and bill references, rejects conflicting duplicates and caps cumulative application at both credit and bill balances. Posting and application can advance while an unawarded remainder stays under human review.

## Agent and model boundaries

- The actual tool-free Claude extraction of public Atlassian terms is recorded with model/session identity, prompt and source hashes. `onboarding_rules` compiles a restricted manifest. `onboarding` stores an immutable version, independent validation results, shadow history and reviewer transitions. A changed governing basis invalidates approval. Customer plan overlays are separate from public templates.
- `intelligence` consumes an actual verified public-only model extraction and evidence-investigation plan. Explanation atoms are selected by the model and rendered against current case facts. The runtime guide answers within that vocabulary. Free-text questions, private contracts, Ramp records and real account logs are never forwarded. This is a constrained contextual guide, not open-ended document interpretation.
- `disputes_claimant` and `disputes_vendor` have separate evidence stores. The independent simulator assesses the actual submitted packet. The oracle was committed before either runtime party; a seeded defect test checks that agreement with the claimant does not define success. The simulator is deterministic. It does not contact a vendor.
- Twelve initial and follow-up design packets plus a release-hardening packet went through tool-free independent Opus review. Each ADR identifies its own response. Model advice cannot authorize a payment, approval or claim.

## Storage, authorization and replay

Immutable case snapshots and hashes, dispute cases, receipts, policy revisions, adapter events, credit transitions and short-lived session digests are stored in SQLite. Transactions and unique keys make retries safe. The receipt includes the approved packet digest; corrected or new content needs its own authorization. A separately approved automated initial filing is limited by evidence, replay scope, configured ceiling and current policy. The reviewer separately controls supplement submission, adapter promotion and reconciliation. Observe mode disables these actions. Local synthetic and public-source demos have one fixed tenant, `bears`.

`LIVE_RAMP_SANDBOX` identifies an actual sandbox-origin observation. Cached observations also receive `DETERMINISTIC_REPLAY`. `LIVE_VENDOR_PUBLIC` records the origin of public terms/status evidence and does not establish a customer's affected service. `SIMULATED_VENDOR` and `SYNTHETIC_CUSTOMER` remain visible in the ledger. `UNAVAILABLE` distinguishes unverified provider evidence from an observed zero.

The fast path runs without any provider or model credentials. Refresh utilities are separate from serving. Saved observations retain capture timestamps; replay business clocks are fixed by scenario while operator audit timestamps record when local actions occur. Rollback uses a prior approved artifact or revocation, never alteration of historical rule or receipt evidence.

## Deployment envelope

One process, one local operator workspace, no payment or production provider transport. SQLite plus a local capability link is suitable for reproducing the demonstration. Production requires an identity provider, delegated tenant grants, protected storage/audit, monitoring, rate controls, provider-specific transport approval, retention policies and validated live customer agreements. Multi-replica workers are outside this deployment contract.
