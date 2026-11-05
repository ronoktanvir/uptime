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

The source can state that this SLA controls a conflict solely within its own subject matter. That narrow precedence operator requires the exact controlling phrase and scope from its source block. A private governing_terms attestation must identify the account agreement, public source SHA-256 and effective date, and the local evidence reference and digest. The attestation must verify that scope, measurement, exclusions, tiers, fee basis, rounding, filing and remedy have no governing amendment. Independent expectations and the authenticated interpretation action still gate approval. An external reference that adds terms, eligibility requirements or definitions remains unsupported.

An explicit account restriction or contractual noncompliance can be a causal downtime exclusion or a filing precondition. The source must support that specific effect. Each required condition needs a scoped local finding with account, agreement, resource, month, reference, verified status and finding. A causal finding subtracts only the time covered by linked observations. An established filing bar preserves the service result and returns no claimable amount. Unknown status or unresolved compliance terms yields missing evidence. Compliance findings must identify the locally reviewed terms and their digest.

Stable operator labels can bind to literal symptom, cause, exclusion, fee category or required request phrases. Each binding retains its source block and digest. Local observations can use the stable service predicate or the exact phrase.

## Rejected public proposals

A rejected public-only CLI extraction writes a separate create-only diagnostic receipt below output-dir/rejections. Its content address covers the raw typed public proposal, source digest, model identity, session, profile, validation reason and timestamp. Runtime candidate intake never loads the rejection directory. To revalidate a receipt offline, run the CLI with --document, --approved-sha256 and --replay-rejection. The result reports the historic refusal and current validation result. A diagnostic replay has no promotion capability.

## Evaluator revision and zero-value credit

A candidate version includes a semantics revision derived from the installed compiler, evaluator, registry and shared calculation source files for that family. Artifact, active binding and new case receipts each retain that revision. A deployment with a different revision, including a conservative change to the same files without semantic effect, disables current activation and dispatch until the document is reinstalled, independently tested and explicitly reviewed. Pre-revision records follow the same rule. Historical receipts retain their original observations, amounts and available provenance. Rollback cannot restore an incompatible evaluator.

An affected fee of zero, or a credit that becomes zero under a source-declared rounding rule, has no claimable amount. A qualifying outage and timely filing can remain separately established. Where the agreement has no settlement rounding rule, the interpreter preserves a positive fractional-cent estimate.
