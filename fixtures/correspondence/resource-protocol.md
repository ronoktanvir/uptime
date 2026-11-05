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

Conditional resource clauses accept maintenance_evidence from the customer connector and prior_credit_evidence from billing. Each monthly statement carries source_ref, observed_at, complete and records. Both require exact scope, a complete statement and observation on or after month end. An explicitly complete empty list establishes that the source found no matching entries. A missing statement leaves the condition unverified. A maintenance entry has ref, account, resource_id, start, end and announced_at. A previous grant entry has ref, credit_id, agreement, account, resource_id, month, currency, amount_cents and state set to issued. Duplicate issuance identifiers and inconsistent scopes invalidate the statement. When prior issuances exist, a new signed monetary message needs a distinct credit_id to book a further award.

A resource fee line may report gross_cents, discount_cents and discount_ref with amount_cents as the net charge, or mark a directly verified net charge amount_basis net_after_discounts and identify its discount_ref. Only a governing after-discount fee clause authorizes that interpretation. The filing proof for a submitted supplement uses its actual dated local receipt, its exact channel and fields, and the original receipt reference.
