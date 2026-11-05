# Uptime V4 engineering status

Uptime is connected to the Ramp demo the user opened. The new app reads the same bill UUID visible in Ramp and has a verified `bills:write` grant. The first native write is still pending. The contract and financial engines are implemented for bounded families; independent evaluation exposes substantial remaining language and source-meaning gaps. Passing regression tests is not production-readiness evidence.

## Completed Northwind integration

The authored Northwind workflow now completes all 11 signed service actions in the real browser: claim, missing-evidence denial, acquired and separately verified log, approved follow-up, award, Local ledger posting and April application. January's USD 2,400 credit reduces April's USD 11,000 invoice to USD 8,600. March's USD 1,000 price finding stays open. CalyxQuay is active with its version hash and 14 recorded lifecycle events, including rollback and reactivation. The actual reviewer remains scripted. [Current checkpoint](NORTHWIND-INTEGRATION-STATUS.md) · [Browser proof](validation/northwind/browser-verification.json) · [Setup and resume](NORTHWIND-WORKFLOW.md)

The independent current-fee recheck passed all three adapted original probes at `844e652`. The actual browser then found a separate HTMLCollection action bug; `3f5b856` repairs it and adds a real Chrome regression. The completed workspace survives restart with the same credit/application IDs and outstanding balance. User-requested stop interrupted the first final verification attempt; the resumed full regression passed **2,949 tests, 1 warning in 218.30s** at `3f5b856`. [Full receipt](evidence/verification-3f5b856.json) No earlier failed or interrupted run is recast as a pass.

Native proof remains blocked. Automatic approval review rejected the independent native-posting retest with the stated reason **possible cybersecurity risk**. That qualification runner remains disabled and unmerged; no actual Ramp write has occurred. The successful local ledger flow does not close this gate.

## Verified Ramp connection

The user created Uptime in the signed-in sandbox, approved six read scopes plus `bills:write`, and approved protected local credential setup. Exact-object verification succeeded through the new app. The original credentials returned HTTP 404 for that browser bill; the provider business UUIDs differ. The original profile, database and captures remain intact. A separate profile and tenant prevent cross-business reuse.

The new capture is `67f0c9b50391d5b5624930e50b70c9e44ffa2ca93cd8609cb99fa11b7d2657d8`: six complete bill reads, twelve sampled vendor records, twelve sampled transactions, twelve sampled purchase orders and eleven approval observations. Broader inventories are truncated. Agreement, vendor-credit and bill-comment queries completed empty. The API returned an exact `bills:write` grant; no native comment, draft mutation, approval, payment or credit application has been attempted. [Connection evidence](evidence/native-demo-connection-20261104.json) · [Reproducible setup](RAMP-DEMO-CONNECTION.md)

Ramp remains the system of record. Uptime's companion holds contract interpretation, evidence, onboarding and disputes. The primary native delivery target is the actual bill discussion. A comment informs a reviewer; it is not payment prevention. Blank Canvas additionally needs an actual configured procurement trigger and hosted signed receiver. Customer OAuth distribution, live webhooks and unrestricted embedded pages have not been established. [Supported interfaces](RAMP-FEASIBILITY.md)

## What works and what remains unreliable

- Exact native IDs associate captured bills, vendors, transactions, purchase orders, approvals and available credits. Freshness and query coverage remain explicit. A separate observed-browser association check refuses host, route, UUID and API-response mismatches.
- Deterministic pricing supports its documented amendment, tier, date and exclusion semantics. The observed bills have no usable negotiated agreement or line-level pricing evidence. The existing USD 840 versus constructed USD 800 example is a hypothetical USD 40 difference, never actual savings.
- The guarded native workflow prepares exact-object plans, verifies independent action authority, journals dispatch and reconciles same-thread comments without blind resend. Its full financial release remains unavailable. A separately scoped, fixed sandbox connection-check proposal is under review; it cannot certify the engine or bypass its financial routes.
- Declarative onboarding has real model proposals, immutable refusals, source quotations, overlays, shadow evaluations, named interpretation, activation and rollback. Reproduced whitespace, issuer-authority, polarity, semantic contradiction, stale current-authority and duplicate scope bugs have targeted repairs. The original failed probes remain available. Reviewed bindings and tests do not establish arbitrary source meaning or unseen-vendor generalization.
- Signed disputes support the implemented evidence joins, correct denials, procedural cures, partial-award distinctions and exact follow-up mandates. The finite parser does not generalize to the fresh independent reply set. The source-locked manual interpretation bridge is implemented; customer runtime model inference remains disabled after the public proposal experiments. Financial and action authority remain separate.
- Reconciliation separates estimates, filed claims, vendor-reported awards, independently verified awards, Ramp credit observations and actual bill applications. No real recovered money is established. Independent source pins and economic identity corrections are preserved.
- The advanced companion supports evidence inspection, onboarding, disputes and audit history. A local progress dashboard shows dependencies and dated evidence. An interactive contextual LLM guide, hosted deployment and multi-business OAuth remain missing functionality.

The [capability matrix](CAPABILITIES.md) and [remaining gaps](REMAINING-RISK.md) give further implementation boundaries. No agent-generated key, test identity, model output or sandbox credential is represented as actual human commercial approval.

## Independent measurements

The explicit source-meaning integration and subsequent independent repairs at `e365f52` pass **2,760 tests, 1 warning in 164.64 seconds**. The independent reviewer found three real defects despite a prior 2,751-test passing run: contradictory telemetry meanings could produce USD15.03, revoked cases retained derived current amounts, and stale checks retained current positive results. The original four failures are preserved. The independent repair recheck passes all 13 original/repair controls plus four additional edge controls, including restored valid re-review and unchanged economic identity. [Full test receipt](evidence/verification-e365f52.json) · [Original findings](evidence/semantic-61-independent/review.json) · [Independent recheck](evidence/semantic-61-independent/repair-recheck-e365f52.json)

The dispute interpretation integration at `f83587f` passes **2,684 tests, 1 warning in 146.16 seconds** with `uv run --locked pytest`. Its first run passed 2,677 tests and hit seven setup errors when the local disk filled; the unchanged source passed after space became available. Both logs remain preserved. This verifies the source-locked manual review bridge and bounded public transport regressions, not language generalization. The four public model experiments produced **0/4 fully grounded compatible candidates** under the final validator; customer runtime inference remains disabled. [Integration receipt](evidence/verification-f83587f.json) · [Experiment and limits](DECISION62-PUBLIC-TRANSPORT.md)

Frozen commit `797c3d0` passed 2,422 Python tests, 34 JavaScript tests and all 118 independent audit assertions, with actual browser/socket checks and stable source hashes. Original V3 passed 73 and failed 45 of those audit assertions. The subsequent whitespace correction at `704caa5` passed 2,607 Python tests; the earlier JavaScript and independent audit counts remain attributed to their frozen source. [Frozen evidence](evidence/verification-797c3d0.json)

The corrected studied-vendor eight-case socket cohort now completes **5/8 cases**, with **141/146 checks** passing. Exactly **one** response was submitted; successful refusal checks are not response counts. Three remaining denials abstain at the parser, and an artifact-language miss also prevents its two action stages. The original ten-case cohort remains **2/10 complete, 134/148 checks**, including missing signed original filing material that parser changes cannot supply. All original inputs, gold and failed attempts remain preserved.

The fresh independent 100-reply set is more consequential: **0/50 valid responses recognized**, **50/50 mandatory-review controls safely refused**, and **zero unsafe false accepts observed**. The independent harness separately passes all **72 public expectations** (18 supported and 54 review controls), so interface parity does not explain the private result. Safe abstention alone does not establish useful discrimination. The fixed February 2027 / USD 37.50 context limits the evaluation further. [Independent result](evidence/independent-replies-532c8d8.txt) · [Public harness parity](evidence/public-reply-harness-532c8d8.txt)

The third public-source extraction remains historically rejected. After bounded whitespace fixes, its unchanged most recent proposal validates offline; no accepted artifact or activation was manufactured from that result. Source-label probes separately reproduce incorrect USD 12.51 shadow eligibility from adverse semantic inputs. This is a genuine correctness risk, distinct from incomplete vendor-language coverage. [Onboarding evidence](decisions/reviews/58-implementation-and-label-boundary.md)

Earlier independent financial bugs, their original reproductions and verified fixes remain in [the audit](INDEPENDENT-FINAL-REVIEW.md) and [the independent follow-up](INDEPENDENT-FINAL-FIX-VERIFICATION.md). Historical cloud-filesystem failures and intermediate test failures remain in durable receipts and checkpoint history.

## Active parallel work

1. Native Ramp integration: exact same-account reads and write grants are established. Prepare a narrowly reviewable native operation, obtain the required exact action/policy authorization, then verify the identical object through API and UI. No unsupported financial conclusion belongs in that note.
2. Onboarding correctness: contain source polarity, qualification and alias ambiguity before monetary shadow results; preserve original proposals and customer-specific evidence. Continue genuine public extraction only under its documented authority and provenance.
3. Dispute generalization: implement manual source-locked interpretation plus optional constrained model prefilling, then measure useful positive coverage separately from safe refusal. Do not fit private cases or silently weaken expected outcomes.
4. Integration verification: run appropriate tests after merges, retain source-linked evidence, update the dependency map and publish focused GitHub commits. Authentic terms, actual human promotion, hosted callbacks and customer installation remain separate prerequisites.

Both onboarding and disputes remain high-priority workstreams. The two-minute recording is a deterministic fallback with simulated financial outcomes, not proof of completed native enforcement. [Demo runbook](DEMO.md)

## Durable execution and sharing

The private [GitHub repository](https://github.com/ronoktanvir/uptime) preserves the original history. The working repository lives outside cloud-synchronized Documents; the original cloud copy remains preserved. Credentials, local databases and private evaluation corpora remain outside Git.

The [dependency map](http://127.0.0.1:8780/) is loopback-only and manually updated after verification. Teammates with repository access can run `python3 scripts/serve_progress.py --port 8780` on their own computer. A shared hosted URL requires a separate publication decision. The displayed update time describes a snapshot, not automatic background-agent tracking.

Processes and agents run only while their execution environment is available. Setup and restart steps are documented in [operations](OPERATIONS.md); no indefinite background execution is promised.
