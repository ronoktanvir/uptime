# Legacy dispute replay, V4 remediation

The four synthetic examples retain their original financial outcomes: cured credit $100, correct denial $0, ambiguous claim $100 disputed, and partial award $80 with $20 disputed. They exercise the ordinary Twilio Services APIs availability branch of the archived April 9, 2026 agreement. This worker made no external requests or current-term verification; the archive does not confer commercial authority. The implementation supports USD, one continuous whole-minute interval and UTC monthly filing boundaries. Premium plans, negotiated overrides, SendGrid throughput and multi-incident aggregation remain unsupported.

All customer charges, incidents, notices, approvals, exchanges and awards are fixture data. The source agreement is public; fixtures are not live customer proof. The one-supplement limit and 24-hour cooldown are local policies. Requiring supplements within the initial filing period is conservative demo behavior, not a claim that the SLA establishes an independent appeal deadline. C owns the separate general correspondence intake.

## Evidence available at each decision

Preflight checks governing date applicability, scope, authentic document references, all available exclusions, exact invoice identities and fee arithmetic. Each document records `observed_at` and `available_at`. An already available maintenance notice blocks filing, wherever it appears in the dossier archives. Missing arrival metadata never conceals a known notice. The original correct-denial story now uses a notice first observed after initial submission and by the explicitly delayed simulated reply. The cure's component record likewise first arrives after the initial assisted submission.

Invoice lines require canonical ID, kind, USD amount, account, product, region, month, currency, invoice ID and evidence reference. Unsupported fields, conflicts, missing scope, duplicate identities and source-pin mismatches block the claim. An authentic component record still needs its nonblank, matching component ID. Cryptographic identity alone does not establish those semantics.

Source manifests are pinned on trusted local provisioning into append-only SQLite records. Every action rechecks the entire manifest, including missing or changed artifacts. Dossier edits cannot silently replace hashes or remove a known notice. Outbound documents are built from an allowlist before the simulator is invoked; approved digests cover exactly that minimized payload. Receipts retain both the payload and its original source-artifact digests. Document mappings cannot be mutated through their normal mapping interface.

Entitlement is exact: $0.01 of eligible fees yields $0.001. Because this simulator has no express contractual settlement-rounding rule, a fractional-cent entitlement displays HUMAN_REVIEW with no claim action. It is neither rounded into a settlement nor marked ineligible. Decimal contexts are isolated from caller precision.

## Independent counterparty and historical expectations

The claimant reads its dossier, not the vendor's private evidence. The vendor independently checks its tenant/account/vendor/agreement binding, document registry, component identity, dates, incident class, invoice ledger and thresholds. It never reads an expected-outcome oracle. Its extra component request is a simulator-specific evidentiary requirement, not a universally prescribed Twilio attachment.

- `oracle/v1.json` remains byte-for-byte historical at SHA-256 `f74f74098229c949956536fce23c191ff1fe49d0de062f7f6accf0aa108823f8`. It was originally committed at `a01e9f8` before V3 runtime implementation.
- `oracle/v2.json` was committed at `8626fa8` before V4 runtime edits. Its SHA-256 is `7c03ad35241f9756beb00c2c6c244f7429ac4914105aa8549895bae13cad8041`. It preserves all four dollar outcomes and freezes the new negative controls and availability semantics. These are same-team synthetic expectations, not an independent field win-rate measurement.
- `traces/` contains regenerated outputs of the actual V4 replay. Original artifacts remain in Git at `18afaa6`. No observed result was edited to match an expectation.
- `verification/v3-counterexamples.json` and `verification/v4-counterexamples.json` are actual outputs of the same local reproducer against the original commit archive and this branch. The script does not inspect secrets or make network requests.

## Integration contract

The public service API remains `DisputeDesk(path)`, `seed(tenant)`, `cases(principal)`, `case(principal,id)` and `act(principal,id,action)`. Principals come from authenticated server state. The fixtures are independently vendor-bound to tenant `bears`. Seeding another tenant does not grant authority over those vendor accounts. Reads require viewer/reviewer authority; actions require reviewer authority.

A canonical monthly obligation key includes tenant, vendor, account, agreement, obligation type, service, region, period and channel. It excludes local case IDs, incident intervals and content digests. SQLite reserves it before simulator invocation; duplicate/revised case imports cannot dispatch another initial claim. One supplement uses the same obligation with its own action key. Immutable receipt rows have a unique obligation/action constraint. Stable failed requests retry under the same approval and key; a second failure stops in human review. The simulator is pure and has no external side effect.

`policy_dispatchable` now requires an exact approved, complete, minimized, scoped packet and the separate affirmative local grant. The stock cure is incomplete initially and therefore **does not auto-dispatch**. If its later-arriving component changes an approved packet, the returned `refresh-claim` action clears the old approval. A fresh approval can authorize the complete packet. The service's global cap and authorization gate remain separately required. No response or settlement is eligible for automatic dispatch.

Additional wire fields are `Ticket.vendor`, `governing_version`, `obligation`, and `Reply.received_at`. Receipts include `obligation_key`, `payload` and `source_artifact_digests`. Initial submission time remains separate from reply receipt time. A vendor's `WINDOW_CLOSED` code is checked against the initial receipt and local cutoff; disagreement routes to HUMAN_REVIEW. No vendor code alone converts a timely claim into an expired one.

Existing V3 databases retain their historical rows. Missing V4 manifests prevent new actions; seeding does not rewrite stored dossiers or bless their old contents. Use a fresh explicitly synthetic replay database for V4, or obtain source-backed reprovisioning through the integration owner. Render the returned actions instead of hardcoding the original sequence.

## Reproduction

Use the lead's Hypothesis-enabled environment for the new generated checks:

```sh
/private/tmp/uptime-v4.WTuRU4/venv/bin/python -m pytest -q tests/test_disputes*.py --hypothesis-show-statistics
/private/tmp/uptime-v4.WTuRU4/venv/bin/python fixtures/disputes/reproduce_audit.py .
/private/tmp/uptime-v4.WTuRU4/venv/bin/python -m uptime.disputes_replay dispute-cure
/private/tmp/uptime-v4.WTuRU4/venv/bin/python -m uptime.disputes_replay dispute-denial
/private/tmp/uptime-v4.WTuRU4/venv/bin/python -m uptime.disputes_replay dispute-review
/private/tmp/uptime-v4.WTuRU4/venv/bin/python -m uptime.disputes_replay dispute-partial
```

The lead owns dependency/lock updates and must run `uv run --locked pytest` after integration merges. The isolated worker's full-suite result and any out-of-ownership incompatibility are recorded in `V4-WORKTREE-NOTE.md` and `verification/`.
