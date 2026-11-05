# Signed resource evidence and supplemental artifacts

This profile uses the existing authenticated claims route. A reviewer opens a claim under an operator-provisioned binding. Each source sends an independently signed POST to /api/correspondence/claims/{claim_id}/events. The full envelope remains {event_id, scope, body}. Every event repeats the full authorized scope. The tenant and issuer come from the server. The scope component is the private resource ID in the ACTIVE overlay. The vendor name, account, private agreement ID, product and currency must also match.

The server joins facts from the following body kinds to a currently ACTIVE resource-month/1 publication. Every new body kind requires source_ref and offset-aware observed_at. These are source attestations. The server separately records received_at, known_at and available_at. It refuses a future observation. A source reporting a complete elapsed month must have observed it after the month closed.

| Body kind | Authenticated source | Additional required fields |
| --- | --- | --- |
| resource_status | status | start, end, complete, intervals |
| resource_attribution | customer | start, end, complete, causes, exclusions |
| resource_invoice | billing | itemized_complete, lines |
| billing_calendar | billing | cycles |
| filing_material | customer | channel, fields |
| artifact | customer | artifact_ref, artifact_type, body_sha256, content |
| status_verification | status | artifact_ref, artifact_type, body_sha256, linked_ref |
| billing_verification | billing | artifact_ref, artifact_type, body_sha256, linked_ref |

Resource_status and resource_attribution cover the exact complete service month. Resource_status.intervals contains {ref, resource_id, start, end, symptom}. Resource_attribution.causes contains {ref, resource_id, start, end, cause}. The sources must give the same ID, resource and interval for each observation. Exclusions are separate {ref, resource_id, start, end, cause} rows. Supply [] for a complete month with no exclusions. Unknown responsibility, inconsistent references or incomplete coverage prevent filing. Published service symptoms, provider causes, contractual exclusions and approved aliases determine which intervals count. The interpreter unions the qualifying intervals and subtracts the union of exclusions at microsecond precision.

Resource_invoice.lines contains {ref, resource_id, month, kind, amount_cents, currency, fee_line_ref?, category?}. Supported kinds are resource_service, tax, support, one_time and other. Amounts are nonnegative integer cents. The entire submitted statement must match the enrolled resource, service month and currency. A positive service line must match the approved fee_line_ref, and published categorical exclusions require a category on each service charge. The signed billing source classifies the items. The interpreter determines the eligible basis and applies a cent rounding convention only when the approved contract establishes one.

Billing_calendar is required when a cycle-based deadline lacks a published or enrolled calendar-month definition. Its cycles array contains {ref, start, end}. The signed schedule must contain exactly the contractual number of successive cycles, starting at service-month end. A published inclusive instant remains eligible through that instant. The API reports the first excluded UTC microsecond as filing_cutoff. A whole-day rule keeps the entire last day open.

Filing_material supplies the exact published channel and an array of {name, refs}. Each required claim field appears once. Every value must name an actual account, invoice, resource, incident, source or row in this same claim. The locally verified future packet includes the resulting allowed field names/references and published channel. The physical destination is always the isolated local simulator. A receipt exists only after reviewer approval and submission. A priced contract result remains an estimate until the separately authenticated vendor answers.

## Example evidence bodies

The bodies below illustrate independent roles and data shapes. Each uses the same signed claim scope. Complete the contract, overlay and source enrollment independently.

~~~json
{
  "kind": "resource_status", "source_ref": "status-june-61", "observed_at": "2026-07-01T02:00:00Z",
  "start": "2026-06-01T00:00:00Z", "end": "2026-07-01T00:00:00Z", "complete": true,
  "intervals": [{"ref":"ls-1","resource_id":"station-21","start":"2026-06-05T00:00:00Z","end":"2026-06-05T08:00:00Z","symptom":"rejected samples"}]
}
~~~

~~~json
{
  "kind": "resource_attribution", "source_ref": "customer-june-18", "observed_at": "2026-07-01T03:00:00Z",
  "start": "2026-06-01T00:00:00Z", "end": "2026-07-01T00:00:00Z", "complete": true,
  "causes": [{"ref":"ls-1","resource_id":"station-21","start":"2026-06-05T00:00:00Z","end":"2026-06-05T08:00:00Z","cause":"instrument gateway failure"}], "exclusions": []
}
~~~

~~~json
{
  "kind":"resource_invoice","source_ref":"invoice-june-71","observed_at":"2026-07-01T08:00:00Z","itemized_complete":true,
  "lines":[{"ref":"june-11","resource_id":"station-21","month":"2026-06","kind":"resource_service","fee_line_ref":"inv-resource-group","currency":"USD","amount_cents":10004,"category":"monthly usage"}]
}
~~~

~~~json
{
  "kind":"filing_material","source_ref":"local-preparation","observed_at":"2026-07-01T09:00:00Z","channel":"claims@example.invalid",
  "fields":[{"name":"station identifier","refs":["station-21"]},{"name":"log references","refs":["ls-1"]}]
}
~~~

## Requests, corrections and allowed disclosure

A vendor message can request a resource log, invoice detail, scope mapping or an explicitly identified attachment. An ambiguous or unsupported request goes to review. A proposed artifact type or ID cannot supply a fact or authorize sending. The reviewer sees evidence metadata, observation/availability timestamps and the original incoming message. Locally stored attachment text is excluded from the case view and the packet.

A customer sends an artifact containing its private content and SHA-256 over its exact UTF-8 bytes. The supported artifact_type values are resource_log, invoice_detail and scope_mapping. The bytes must hash to body_sha256. A second source independently attests the same artifact_ref, artifact_type and body_sha256. Resource logs and scope mappings require status_verification linked to an authenticated status report or interval. Invoice details require billing_verification linked to an authenticated invoice or line. The linked_ref can identify an event, source or row in that claim. A document alone, a digest alone, a verifier from the wrong channel, a wrong reference or a conflicting hash cannot support a rebuttal.

At least one side of the verified pair must be new to the original packet. A reviewer then approves one supplement, subject to the cooldown and original contractual filing window. The identified disclosure contains only ref, type, sha256, verifier_digest and record_digest. The original private content never reaches the simulator. If a vendor explicitly rejects a scoped receipt using a different account, resource or invoice ID, the claimant compares that assertion to the signed source scope and original packet. A verified mismatch can support one reviewer-approved correction that identifies the verified field. An unparseable, hedged or conflicting assertion goes to human review.

Tests in tests/test_correspondence_resource.py exercise this protocol over the authenticated server using independent fixture signers, manually staged synthetic terms propositions and an explicitly named reviewer. They do not poll a vendor, query a provider, or send claim material outside the local application.

The optional offline resource counterparty in uptime.correspondence_vendor.adjudicate_resource accepts a private resource ledger, independently measured service and exclusion intervals, its own fee categories and tiers, filing cutoff and a pre-verified attachment hash. It sweeps interval boundaries independently of the published evaluator, computes the amount, and returns an ordinary message. Deliver that message separately with the authenticated vendor identity. The independent regression reproduces the 433-minute result and USD 12.51 award without giving the counterparty the claimant's event store or evaluator output.

An ACTIVE resource contract with account-status or compliance conditions also requires a customer-signed account_conditions event. It carries source_ref, observed_at (on or after the end of the service month), and findings. Each finding has an operator-defined ref, the published op (account_restriction or contract_noncompliance), finding (clear, applies, or unresolved), and affected_refs. Causal exclusions name contributing incident interval references. A contract_noncompliance finding also supplies reviewed_terms with ref, sha256 and content. The desk verifies the actual local bytes and keeps them out of outbound packets. Missing, overlapping or unresolved findings withhold eligibility. A definite finding can block filing or remove only its scoped intervals, as the published clause requires.

Submission fields must cite evidence of the kind requested by the clause. For example, a station identifier must be the enrolled resource, and a log reference must resolve to the status report or its incident rows. A fee-line ID from the same case cannot stand in for an incident log. Unknown or ambiguous field meanings require review.

A definite vendor assertion that measured availability met the applicable threshold can support one draft correction when the current active contract and independently joined records establish a breach at the original claimed amount. The supplemental packet carries counted and total service-month microseconds, the source digests, the published terms digest and the original receipt. Ambiguous language or a conflicting evaluation leaves the case for review. The reviewer still controls both approval and local submission.

For monetary replies, an affirmative grant must identify an amount and a credit for this filing. A quoted example, another beneficiary, a budget cap or an unrelated fee cannot establish an award. A message can restate the original claim and separately deny the remainder if those amounts reconcile exactly to the filed amount. Ambiguity preserves the raw incoming note and routes the case to review with no new award.

Conditional resource clauses accept maintenance_evidence from the customer connector and prior_credit_evidence from billing. Each monthly statement carries source_ref, observed_at, complete and records. Both require exact scope, a complete statement and observation on or after month end. An explicitly complete empty list establishes that the source found no matching entries. A missing statement leaves the condition unverified. A maintenance entry has ref, account, resource_id, start, end and announced_at. A previous grant entry has ref, credit_id, agreement, account, resource_id, month, currency, amount_cents and state set to issued. The same issuance ID with the same scoped amount counts once across statement references. Conflicting amounts or scopes invalidate the statement. When prior issuances exist, a new signed monetary message needs a distinct credit_id to book a further award.

A resource fee line may report gross_cents, discount_cents and discount_ref with amount_cents as the net charge, or mark a directly verified net charge amount_basis net_after_discounts and identify its discount_ref. Only a governing after-discount fee clause authorizes that interpretation. The filing proof for a submitted supplement uses its actual dated local receipt, its exact channel and fields, and the original receipt reference.

An original_filing_receipt and a supplement_filing_receipt are vendor-signed **historical evidence**. Both use source_ref, observed_at, receipt_id, received_at, submitted_to and fields. A supplement must have an original_ref that names the original vendor receipt. Observed time must be at or after receipt time. The customer connector independently supplies the filing_material, and the contract and signed source records validate its field references. The vendor receipts identify which fields the vendor actually received and when. A supplement may arrive in the local inbox first. Missing original proof holds the case until both sides can be joined.

The historical evidence path reserves the existing resource-month obligation and displays HISTORICAL_FILING. It cannot send another claim or declare a new award. Its claimed and awarded entries stay zero until a separate authorized financial path establishes them. A timely supplement can establish that the original met the active remedy's documentation rule. A later delivery fails that rule even if all required material eventually appears.

A vendor-signed message can name the current independently witnessed receipt_id as its receipt_id. A historical supplement must have the exact original_ref, channel and chronology. A new substantive message on an earlier receipt fails. An exact redelivery returns its existing receipt. Multiple substantive replies to the same receipt preserve the conflict for review.

When a governing same-deadline supplement clause allows it, the desk can draft one factual response to a timely, independently witnessed original. A request for a missing filing item must match a published field. Customer-signed filing_material identifies its proposed references and independent source evidence must actually support them. A mistaken time-bar objection can likewise be answered from the original receipt and published cutoff. Both paths use ordinary signed approve-response / submit-response actions, the local cooldown, the original cutoff and the same economic reservation. The local packet states purpose procedural_evidence_only and requests USD 0.00. It names its actual external predecessor, source commitments and relevant findings. A subsequent message must name the local reply receipt. Procedural correction does not establish the month's monetary entitlement or authorize a credit.

Field references are typed by their actual cited meaning. A month field names the scoped service month. An interruption interval or covered cause names its signed event-level source; cause attribution must match the observation's resource and interval. A valid-request failure may name a signed status observation that explicitly attests that fact or a customer request_evidence record. That record contains ref, resource_id, interval_ref, requested_at, valid and failed. It must identify a failing valid request inside a corroborating status interval. Billing evidence needs a positive charge on the scoped resource and approved fee-line mapping. Partial incident reports can prove a filing item while the financial preflight continues to report insufficient full-month evidence.

## Regional monitors and portal response clocks

A reviewed regional subscription must bind the account, agreement, product, plan, region, governing version and complete active month through `overlay.subscription_record`. Its region matches the signed claim scope. `customer_telemetry` uses a customer source and `provider_telemetry` uses a status source. Each report carries `source_id`, `start`, `end`, `complete`, `records`, `source_ref` and `observed_at`. Each row contains `ref`, `account`, `product`, `region`, `resource_id`, `start`, `end` and the source-defined `status`. The reports require independent signing identities. Empty complete streams additionally require `no_events_verified: true`. The customer report includes `exclusions_complete` and `exclusions`. When the published clause requires a custodian, a separate provisioned customer-role signing identity delivers `custodian_attestation` with `source_id`, `monitor_ref`, `source_ref` and `observed_at`. This attestation identifies the actual customer monitoring report. The evaluator intersects qualifying intervals from both streams and then subtracts the verified exclusions.

For paid net recurring charges, each affected resource-invoice line supplies `product`, `region`, `recurring`, `payment_state`, `refund_ref` and `refund_cents` alongside the existing discount data. Gross cents minus discount cents minus refund cents must reconcile to `amount_cents`. The published contract determines whether these predicates apply.

An original portal receipt additionally supplies `ticket_id`. A distinct vendor-signed `portal_response_receipt` supplies `original_ref`, `ticket_id`, `message_ref`, `response_kind` (`denial` or `evidence_request`), `delivered_at`, `source_ref` and `observed_at`. Its `message_ref` names the independently delivered freeform message event. The clause determines which response kinds start the correction window. Both original and response receipts must have the same scope and ticket, and the original must satisfy the original filing deadline and required initial fields. The actual response delivery time starts the correction window. A supplemental receipt or approved local procedural reply retains both `original_ref` and `response_ref`. An ambiguous note, different ticket, mismatched message, late original or expired correction deadline withholds response authorization. A complete financial record may become eligible after the factual cure. An incomplete month continues to withhold entitlement.

`tests/test_correspondence_regional.py` exercises these event arrivals through the authenticated local HTTP API with fixture HMAC signers and an explicitly scripted reviewer. The tests cover the inclusive correction boundary, independently signed custody, scope errors, missing receipt, incomplete month, refunds and idempotent dispatch. A real configured connector uses its separate Ed25519 grant through the same typed event entry point.

## Whole-service aggregate records

A reviewed `aggregate_monitor` contract selects the service-month join. Its fixed UTC month, fixed filing instant, recurring fee and source integrity rules control the evaluation. The signed scope still names the enrolled account, agreement, service, month, invoice and source binding. The economic reservation covers the whole service, so component aliases share a single filing entitlement.

`service_monitor` is delivered by the status connector and `service_invoice` by billing. Each body carries `source_ref`, `observed_at`, `recorded_at`, `plan`, `complete`, `content` and `content_sha256`. The digest is the canonical `uptime.contracts.fingerprint(content)`. The source record must be dated after the completed month and before its observation. The monitor content is `{source: "simulated_vendor", unavailable_minutes: number_or_decimal_string}`. An integer, finite JSON number or exact decimal string must represent a nonnegative duration at microsecond precision. The signed JSON scalar and content hash are preserved; booleans and finer precision are rejected. The invoice content is `{currency: "USD", paid: true, lines: [...]}`. Each fee line includes `ref`, `kind`, `category` and `amount_cents`. The deterministic evaluator applies the actual published recurring-line mapping and excluded categories. A missing, incomplete, wrong-plan, unpaid or hash-conflicting source leaves eligibility unestablished.

The original local packet uses the reviewed proposal timestamp for preflight and the actual immutable submission receipt for subsequent evaluation. Imported existing filing receipts instead preserve their observed arrival. An independently delivered vendor message must name the current receipt. Signed record totals support a bounded correction to a mistaken duration or threshold assertion. Partial awards remain in review with the disputed remainder, and ambiguous correspondence retains its incoming text without authorizing a response. `tests/test_correspondence_service.py` exercises these paths through the local authenticated API and checks that an alias cannot dispatch a second whole-service claim.

A witnessed aggregate original can also receive a correct denial. The desk accepts a definite late-filing assertion only when its signed arrival is actually outside the fixed deadline. It accepts a definite threshold assertion only when the independently joined complete source records produce the contractual zero rate for a timely original. These paths retain the historical filing and leave both local claimed and awarded amounts at zero.

## Original contract-version provenance

An `original_filing_receipt` may include `contract_version`, the governing scoped version that the independent source attests for the original filing. The claim detail API exposes the currently reviewed value as `contract_version`, using the same convention as an approved local packet's `version`. A supplied pin must match those scoped terms when the source delivers the original. The application includes the exact supplied value in the signed event body, immutable event digest and displayed receipt metadata. The source must attest the original version from its records. Reading the current version alone establishes no historical fact.

Historical receipts that omit the field remain readable. Actual monetary attribution requires the original's explicit version pin to equal the independently registered claim scope. A later publication or registration cannot fill a missing original pin. A replacement pin conflicts with the existing immutable original receipt. Supplements retain their original receipt reference. Version continues to be excluded from the canonical economic obligation key, so publication revisions cannot create a second filing entitlement.

A proposed factual rebuttal requires complete coverage of the incoming message. Every substantive clause must fit the same supported factual interpretation, including any text surrounding the recognized cue. Short denials, courtesy closings and bounded sender signatures can accompany it. A separate settlement, commercial condition, termination assertion or other unmatched clause keeps the complete incoming message in human review. The historical missing-field path applies the same coverage requirement before selecting any filing evidence.

An original receipt can additionally pin `contract_source_sha256`, the SHA-256 of the exact governing source document. The read-only claim view exposes the currently verified digest under the same name. A supplied original digest must match that document when ingested, remains part of the independently signed event, and appears on its historical receipt metadata. Actual attribution requires both the semantic version and the original document digest. This distinguishes a substantive source document from another document with the same interpreted economics. Missing historical pins remain explicit, and neither pin changes the canonical obligation key.

The retained v2 economic identity uses `/` as a resource/region separator. New reviewed resource scopes containing that delimiter are quarantined for manual reconciliation. The ordinary resource name `aggregate-service` is reserved for the existing whole-service profile. Safe identifiers retain their exact existing keys. Historical receipts, case IDs and reservations stay intact. An affected archived evaluation remains readable as `REVIEW_REQUIRED`, retains `recorded_amount` and the original snapshot, and exposes no current amount or economic grouping key. Any stage with such a positive historical contribution has an unavailable aggregate total rather than treating the contribution as zero. New drafts also refuse an already reserved economic key before writing an inbox event; dispatch independently checks exact stored owner, scope and predecessor. The application does not assign a replacement identifier or create a new filing key automatically. A region contributes to the key only when the reviewed subscription defines separate regional coverage. Other location labels do not enter the key. Exact resource and region identifiers are not case-folded, Unicode-normalized or URL-decoded; slash look-alikes therefore remain distinct exact values.
