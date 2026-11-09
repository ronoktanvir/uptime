# Vendor catalog and monthly availability adapters

The catalog accepts source document text and a separate tenant account overlay. It extracts a bounded monthly availability contract family, runs reviewer-supplied expectations in shadow, and requires authenticated review before activating new workbench evaluations. Catalog operations are local. Every customer observation and resulting credit estimate is explicitly synthetic.

## Application interface

The host mounts uptime.vendor_api.make_router(db_path, actor, reviewer, check_write, mutex). The host supplies authenticated tenant dependencies, same-origin action proof, the observe-only policy, and the shared mutation lock. Candidate and test requests need a bounded JSON body limit larger than the legacy 4 KiB action limit.

| Route | Behavior |
| --- | --- |
| GET /api/vendors | Lists installation IDs, vendor identity, revisions, and current activation |
| GET /api/vendors/{installation_id} | Shows cited rules, private overlay, tests, review actions, and audit |
| POST /api/vendors/{installation_id}/candidates | Extracts a document, validates an overlay, and creates a shadow revision or quarantine |
| POST /api/vendors/{installation_id}/tests | Runs externally specified expected outcomes |
| POST /api/vendors/{installation_id}/actions/{returned_id} | Consumes a subject-bound, revision-bound action with an empty JSON body |
| POST /api/vendors/{installation_id}/evaluate | Uses the current active adapter to persist a workbench evaluation |

The path identifier is a tenant-scoped installation slot. One slot has one account/product/plan overlay. Multiple slots can refer to the same explicit vendor identity and public contract. A public manifest can define multiple products, plans and tiers. Updating an overlay in a slot creates a new governed candidate.

A candidate body contains document and overlay. The document contains name, uri, classification and text. Accepted classifications are public and synthetic_public. The latter permits a synthetic URN as provenance. HTTPS URLs are retained as citations and are never fetched by intake. A supplied classification and URL do not establish externally verified provenance or currentness.

The overlay requires agreement, account, product, plan, effective_from, effective_until, fee_line_ref and currency. Only USD affected monthly fees are implemented. An optional private override has filing_days, source_ref and an explicit quoted filing clause. It changes the filing window only for this agreement/account/product/plan and finite overlay interval. A mismatching quoted window is rejected. Private amendments remain local.

## Supported contract family

The strict offline extractor recognizes independently changing vendor and agreement names, dates, monthly UTC availability, exclusive percent thresholds, descending credit tiers, calendar-day filing windows after month end, and future invoice credits based on affected monthly fees. Percentages become integers with six fractional decimal places. The evaluator compares exact integer ratios and preserves fractional-cent modeled estimates.

The parser supports concise ordinary clauses and Markdown percentage tables. For example, a source can say “For Data Lake on the Advanced plan, monthly availability below 99.9% earns a 15% service credit.” A table can name product, plan, monthly availability below, and service credit. Unsupported units, comparators, fee bases, overlapping tiers, qualification clauses, or unconsumed source text quarantine the candidate.

An explicit public start date may have a null end when the source provides no termination date. Every overlay must provide a finite inclusive interval. Evaluations require the whole calendar month to fit both intervals. Each case retains source digest, intake receipt time and exact version. The receipt time records when this text arrived, with external currentness explicitly unverified.

## Tool-free model extraction

The application never sends uploaded documents or overlays to a model. An operator can separately stage a public-only model proposal after approving the digest of the exact UTF-8 document text.

~~~sh
python -m uptime.vendor_model \
  --document /absolute/path/public-document.json \
  --approved-sha256 EXACT_TEXT_SHA256 \
  --output-dir /absolute/path/operator-owned-extractions
~~~

The command invokes Claude Opus 5.5 with tools disabled, strict MCP configuration, an empty working directory and no session persistence. Only document text and extraction instructions enter the prompt. The private overlay is absent from the input type. The child process can inherit the Claude CLI's own OAuth credential for this explicitly requested call. The environment omits Ramp credentials and provider-host overrides. Prompt and receipt contain no authentication values.

Set UPTIME_PUBLIC_EXTRACTIONS to the operator-owned extraction directory to consume the digest-named receipt. The application checks source digest, proposal digest, model identity, full source coverage, exact spans and locally interpreted values. Otherwise it parses the new input offline.

A reversible profile broadens ordinary prose through model-proposed typed propositions. It requires CLI --allow-propositions and app environment UPTIME_MODEL_PROPOSITIONS=1. The default strict path remains available. The broader profile accepts cited scopes and two-column tables plus variable prose. Deterministic guards check percentages, dates, units, exclusive operators, product/plan bindings and unsupported qualifiers. These guards do not establish full semantic equivalence. The returned interpret action requires an authenticated reviewer to accept the cited interpretation before approval. Its actor and revision are recorded.

## Reviewer gates and dispatch

The test submission has revision and tests. Each test contains a unique name, facts and expected with outcome plus the exact string amount for eligible cases. Tests must contain a positive and a refusal. Every expectation and generated arithmetic check must pass. A failing suite exposes no approval action. Generated checks exercise arithmetic boundaries and do not substitute for independently authored contract expectations.

Facts bind agreement, account, product, plan, month and fee_line_ref. Synthetic observations include eligible_downtime_minutes, monitor_source equal to simulated_vendor, month_complete, exclusions_removed, monthly_fee_cents and offset-aware received_at. Optional monitor_ref, fee_ref, monitor_month and fee_month bind explicit evidence references and periods. Missing authoritative measurements, incomplete periods, mismatched scopes and public status alone cannot create an eligible estimate.

Approval records the authenticated principal. Activation requires the same approving principal. Test identities are labeled scripted_test. Other reviewers are labeled authenticated_reviewer, without inferring human physical presence from a subject string.

Source or overlay replacement suspends dispatch and resets review. Malformed intake quarantines the slot. Restored sources require fresh revision-bound actions. Explicit revoke and review cannot resurrect approval links. Rollback restores a previous version only when source, overlay and independent suite remain compatible. Otherwise it disables dispatch.

An active adapter writes through storage.persist_case in the lifecycle transaction. Obligation identity stays stable when observations change, so corrections append revisions instead of duplicate portfolio rows. Historical cases survive rollback. vendor_registry.resolve_case(path, principal, case_id) requires the current active version for downstream workflows. require_active=False permits explicit historical inspection. active_binding(path, principal, installation_id) resolves the trusted current manifest and overlay.

Evaluation case IDs retain their installation-specific history. Financial grouping uses the shared filing identity for the tenant, contractual vendor, account, agreement, service, month and source-defined remedy. Resource remedies retain the resource identifier and include region when the supported subscription clause establishes separate regional coverage. Aggregate remedies retain `resource-month/aggregate-service`. Installation aliases and reissued versions share an economic key. Distinct covered resources and regions contribute separately, while conflicting estimates for one key make the total nonadditive. Historical projection verifies the original archived artifact and bound observations and preserves every stored snapshot and receipt.

Filing remains distinct from issuance, award, posting and application. The generic interpreter establishes as-filed synthetic eligibility estimates. Vendor issuance remains unconfirmed. Legacy Jira separately reports timely filing and blocked or unconfirmed account-standing issuance conditions.

## Reviewed resource-month agreements

The resource-month/1 profile adds source-defined qualifying symptoms, provider causes and exclusions, an affected resource fee basis, graduated rates and an explicit filing endpoint. The public-only CLI uses --profile resource-month --allow-propositions. Resource extraction sends ordered public block IDs with their text. The model returns typed effects for every ID in order. The application reconstructs quotes from immutable source text, verifies every block offset and SHA-256 digest, and rejects missing or duplicate IDs. Every non-whitespace character belongs to a quoted span containing typed propositions, an explained nonmaterial classification, or an unsupported finding. Unsupported material quarantines the candidate. The interpretation review presents all spans in order. Acceptance binds the exact source, model output, private overlay, test results and lifecycle revision.

Opus review 25 identified an omission risk when a proposal quotes accurate sentences but leaves out an incorporated condition. The interpreter rejects unaccounted source text and unresolved governing references. Review 28 distinguished source-specific service definitions from arithmetic. The model must supply source-grounded symptom and cause literals. Local mappings may connect customer vocabulary to those literals. The interpreter then computes downtime independently from account/resource evidence in UTC. Human review still determines whether the full set of propositions captures the governing meaning. The synthetic regression contract uses weather instrument stations and hand-calculated overlap, cutoff and rounding results. Independent blind results are recorded separately by the integration lead.

The public period can be a resource UTC calendar month, a calendar month with no public timezone, or a resource billing month. A public billing period with no authoritative clock requires a private billing_period containing kind utc_calendar_month, an explicit quotation and a source_ref. The overlay binds resource_id and optional public_product, public_plan and public_agreement. Customer-only aliases and billing evidence remain local. A public end date can remain null while signed account coverage has a finite end.

Resource facts bind agreement, account, product, plan, resource_id, fee_line_ref and month. A complete monitor record contains a synthetic customer or simulated vendor source, monitor_ref, month_complete and intervals. Each interval carries ref, account, resource_id, offset-aware start/end, symptom and cause. The interpreter clips to the month, unions overlapping qualifying intervals, and subtracts overlapping source-defined exclusions. Optional exclusions use the same scope/time identity and a cited excluded cause. Unknown attribution, conflicting duplicate references and public-status-only observations yield missing evidence. Correctly identified records for another resource contribute no time or fees.

An itemized_complete fee_lines array supplies scoped USD cents from resource_service charges. Tax, support, one_time and other lines fall outside the positive service-fee basis. Each qualifying line must have the approved fee_line_ref, either as its own ref or as the explicit group reference. The interpreter preserves the exact estimate unless the source specifies nearest-cent half-up rounding.

An explicit UTC filing time uses the contract's inclusive or exclusive comparator. A whole-cycle deadline requires a verified UTC calendar billing schedule or contiguous, referenced billing cycle records after month end. An unclear contractual endpoint produces UNSUPPORTED_RULE. Source-defined submission channels and required request items require a verified local filing_proof naming the account, resource, matched destination, reference and required fields. A timely receipt and qualifying outage establish an as-filed estimate. Vendor verification remains a separate issuance state. Optional simulated issuance evidence must match the account, resource, currency and exact credit amount.

In-process downstream consumers can call vendor_registry.evaluate_active_db(db, principal, installation_id, facts, expected_version=..., expected_revision=...) inside their existing transaction. It resolves the active artifact, uses its actual overlay, and returns the rule version, revision, source/overlay digests and authoritative evaluation without creating a case. The path-based evaluate_active wrapper provides the same read operation. Case creation still requires the authenticated evaluation endpoint.

## Governing-document conflicts and local account findings

The source can state that this SLA controls a conflict solely within its own subject matter. That narrow precedence operator requires the exact controlling phrase and scope from its source block. A private governing_terms attestation must identify the account agreement, public source SHA-256 and effective date, and the local evidence reference and digest. The digest is only format-checked: it is an operator-supplied reference, not verification against stored signed evidence (accepted finding F6 in [the onboarding trace](v4/ONBOARDING-TRACE-89.md#7-accepted-findings-awaiting-a-semantics-revision)). The attestation must verify that scope, measurement, exclusions, tiers, fee basis, rounding, filing and remedy have no governing amendment. Independent expectations and the authenticated interpretation action still gate approval. An external reference that adds terms, eligibility requirements or definitions remains unsupported.

An explicit account restriction or contractual noncompliance can be a causal downtime exclusion or a filing precondition. The source must support that specific effect. Each required condition needs a scoped local finding with account, agreement, resource, month, reference, verified status and finding. A causal finding subtracts only the time covered by linked observations. An established filing bar preserves the service result and returns no claimable amount. Unknown status or unresolved compliance terms yields missing evidence. Compliance findings must identify the locally reviewed terms and their digest.

Stable operator labels can bind to literal symptom, cause, exclusion, fee category or required request phrases. Each binding retains its source block and digest. Local observations can use the stable service predicate or the exact phrase.

## Rejected public proposals

A rejected public-only CLI extraction writes a separate create-only diagnostic receipt below output-dir/rejections. Its content address covers the raw typed public proposal, source digest, model identity, session, profile, validation reason and timestamp. Runtime candidate intake never loads the rejection directory. To revalidate a receipt offline, run the CLI with --document, --approved-sha256 and --replay-rejection. The result reports the historic refusal and current validation result. A diagnostic replay has no promotion capability.

## Evaluator revision and zero-value credit

A candidate version includes a semantics revision derived from the installed compiler, evaluator, registry and shared calculation source files for that family. Artifact, active binding and new case receipts each retain that revision. A deployment with a different revision, including a conservative change to the same files without semantic effect, disables current activation and dispatch until the document is reinstalled, independently tested and explicitly reviewed. Pre-revision records follow the same rule. Historical receipts retain their original observations, amounts and available provenance. Rollback cannot restore an incompatible evaluator.

An affected fee of zero, or a credit that becomes zero under a source-declared rounding rule, has no claimable amount. A qualifying outage and timely filing can remain separately established. Where the agreement has no settlement rounding rule, the interpreter preserves a positive fractional-cent estimate.

## Signed HTTP rehearsal with external synthetic inputs

Run the following from the repository. Supply the public document object, private synthetic overlay object and independently calculated list of shadow scenarios as separate JSON files. Only use synthetic customer observations. The command starts the real application in a disposable replay database on a newly bound loopback port. It uses the reserved scripted identity for all review actions and reports `human_approval: false`. No vendor communication occurs. An operator may stage a public-only extraction first and select it with the environment variables above.

```sh
python scripts/rehearse_vendor.py --document public.json --overlay synthetic-order.json \
  --scenarios synthetic-review-scenarios.json > rehearsal-receipt.json
```

The output records the source, suite and evaluator digests, actual HTTP statuses, resulting case IDs and financial estimates. The runner verifies that shadow and rolled-back revisions refuse dispatch, an active revision produces the expected results in the workbench and portfolio, and historical case evidence survives rollback. Scenarios for the same monthly obligation deliberately update a single case. A named human uses their own enrolled credential and the gated workspace for a real review decision.

## Resource-level adjustments and supporting records

The resource profile uses exact UTC durations, unions concurrent intervals and preserves fractional time. A typed maintenance exclusion can apply to all overlap with an announced window, or to just the source-defined maintenance cause within the window. A minimum notice interval, when present, must be established by the contract. The evaluator compares the actual announcement time to the original window start before clipping the overlap to the service month. A late or explicitly unannounced window supplies no exclusion.

A resource contract can require net charges after discounts, a deduction for earlier credits granted for the same resource and month, and supplementation within the original filing window. Each new operator has its own ordered source citation. Missing evidence prevents an estimate. A conflicting duplicate credit, a mismatched discount breakdown or an unlinked supplement also prevents a positive result.

| Private evidence | Fields and checks |
| --- | --- |
| Maintenance register | `maintenance_evidence` contains `verified: true`, `complete: true`, `ref`, `agreement`, `account`, `resource_id`, `month`, and `records`. Each record supplies `ref`, `account`, `resource_id`, `start`, `end`, and an offset-aware `announced_at`. A verified row with `state: "confirmed_unannounced"` and a null announcement timestamp explicitly rules out advance publication. |
| Net invoice line | A matched `resource_service` line supplies `discount_ref`. Its `amount_cents` is the actual net amount. Supply either both `gross_cents` and `discount_cents`, which must reconcile exactly, or `amount_basis: "net_after_discounts"` for a directly attested net amount. |
| Prior credit ledger | `prior_credit_evidence` uses the same verified, complete, scoped envelope as the maintenance register. Its records contain `ref`, `credit_id`, `state: "issued"`, `agreement`, `account`, `resource_id`, `month`, `currency: "USD"`, and integer `amount_cents`. Repeated evidence of the same issued credit counts once. An empty verified statement establishes zero for its specific scope. |
| Supplemental receipt | `filing_proof.supplements` is a list of receipts. Each specifies `verified: true`, `ref`, `original_ref`, `agreement`, `account`, `resource_id`, `month`, `received_at`, `submitted_to`, and the source-defined request `fields` supplied in that supplement. It must reference the original filing and match its destination. The original receipt time still governs the first filing. A timely supplement can supply missing fields. A required field supplied after the cutoff gives `LATE_SUPPLEMENT`. |

The case records `service_estimate` before deducting existing credits, `prior_issued_cents` as the amount supported by the scoped ledger, and `remaining_estimate` after deduction with a zero floor. Only a positive remaining estimate can become the case amount. Existing issuance evidence and financial posting remain separate stages.

## Availability formulas expressed in words

The compiler checks the order of operands and their elapsed units. For example, “100 multiplied by one minus covered minutes divided by all minutes in the month” permits two readings without parentheses. The proposed reading scales the available fraction by 100. Under literal arithmetic precedence, zero downtime still gives 100%, but a completely unavailable month would give 99%. The returned `formula_grouping_review` records both expressions, their endpoint values and the source block. A passing independent positive observation must differentiate the two interpretations. The signed interpretation action names the proposed formula, and the registry records the reviewer, exact source version and tested revision. A substituted multiplication, reversed denominator or incompatible units still quarantines intake.

The public-only rejection replay also returns a `diagnostics` array for resource-month proposals. It checks independent blocks and fields and reports any remaining aggregate dependency error. It verifies the historical receipt’s content address, leaves it untouched, and provides no promotion action. Even a proposal that validates under newer code still requires fresh intake and the full independent review sequence.

An operator can explicitly export a bounded public diagnostic attachment during offline replay.

```sh
python -m uptime.vendor_model \
  --document /operator-approved/public.json \
  --approved-sha256 <exact-public-source-sha256> \
  --replay-rejection /operator-approved/rejections/<rejected-receipt-sha256>.json \
  --diagnostic-output-dir /operator-owned/extractions
```

Use the operator-owned directory already selected by `UPTIME_PUBLIC_EXTRACTIONS`. Export creates an immutable report under `public-diagnostics/<diagnostic-sha256>.json` and explicitly selects it through `<source-sha256>.diagnostic.json`. A subsequent signed intake of the exact public source can attach `public_source_issues` to its quarantine detail. The existing vendor detail displays those issues alongside the generic refusal. A repeated intake appends a new event only when its selected attachment changes. Repeated reads preserve the event history.

Reports contain fixed reason codes and byte-checked original public slices, with bounded quote sizes and the rejected receipt's digest. Explanations come from a fixed server table. Private overlay failures retain generic messages, and approved public issues appear independently of overlay success. Model rationale and exception text cannot enter the attachment. Normal intake resolves the exact operator-selected report without traversing rejection archives or invoking a model. Mismatched source hashes, modified quotes, extra fields and stale validator revisions produce the generic refusal. Export requires a currently rejected proposal with exact source-block diagnostics.

Extraction hints and compilation share the existing whitespace normalization, including ordinary NBSP, while provenance retains the original source bytes and offsets. The no-minimum-duration operator accepts bounded affirmative assertions and refuses additional unsupported duration quantities or conditions in the same block. Hyphenation and zero-width characters remain unresolved. Issuer verification requires a source-bound provider process or issuance condition. The legacy claimant-proof combination is retained only with explicit proof language, source-bound filing fields and `request_contents`; every such `verification` label becomes internal `claimant_supporting_proof`. This internal label grants no issuer authority and remains outside the input vocabulary.

## Regional subscriptions and independent monitors

A `subscription` operator binds coverage to an account, service edition, region, accepted contract version and signed interval covering the whole month. The private overlay supplies `subscription_record`. Its `verified`, `signed`, `ref`, `account`, `agreement`, `product`, `plan`, `region`, `contract_version`, `active_from`, `active_until` and `subscription_type` must establish that scope. The observation repeats the region.

An `intersect_customer_provider` telemetry condition requires two complete independent streams. `customer_telemetry` and `provider_telemetry` each contain `verified`, `complete`, `ref`, `source_id`, `account`, `agreement`, `product`, `region`, `resource_id`, `month` and `records`. Each interval supplies its own reference, identities, timestamps and source-defined status. When the source requires custody, the customer statement includes a signed, verified `custodian` binding that recording system to the same identities. Empty streams require an explicit `no_events_verified` finding. Qualifying time is the intersection of the two independently attested streams after each stream's overlap union.

A `cure_clock` measures the contractual elapsed days from an independently verified vendor response delivered on the original ticket. The original proof contains its scoped portal timestamp and ticket ID. Its `response_receipt` identifies the response reference, kind, delivery timestamp, ticket and complete scope. A supplemental receipt cites both the original and response references. The original filing must have been timely and contain its required identity fields. Tests in `test_vendor_resource_scoped.py` provide the complete wire representation and boundary controls.

## Fixed service-month aggregates

A source can instead establish one exact UTC calendar month and make a vendor's account-scoped unavailable-minute report authoritative. The resource extraction profile represents that with `fixed_period`, `fixed_filing`, `aggregate_monitor`, `service_fee` and `record_integrity`. The source's fixed duration must match the real calendar month. An expressed relative filing interval must agree with the absolute cutoff. A noncash-only remedy retains its own issuance label without inferring a future invoice commitment.

The observation supplies separately verified `service_monitor` and `service_invoice` envelopes. Each includes `agreement`, `account`, `product`, `plan`, `month`, `ref`, `recorded_at`, `complete: true`, `verified: true`, `content` and `content_sha256`. The digest is the project's canonical `fingerprint(content)`. Monitor content contains `source: "simulated_vendor"` and `unavailable_minutes` as an integer, finite JSON number or decimal string. Signed intake preserves that scalar's type and content hash. The evaluator converts it to exact integer microseconds and refuses sub-microsecond quantities, negative values and durations exceeding the source month. Invoice content contains `paid: true`, `currency: "USD"` and itemized lines with `ref`, `kind`, `category` and `amount_cents`. One matching `recurring_subscription` line establishes the fee base. Other lines must match source-defined exclusions. A verified scoped `filing_proof` supplies the actual receipt timestamp and source reference. The profile supports these bounded conditions and refuses additional resource conditions that its aggregate evidence cannot establish.
