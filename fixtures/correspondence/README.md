# Independently delivered claim correspondence

The inbox accepts new claim scopes and independently arriving source events through authenticated application routes. It starts with an empty evidence record. A reviewer opens the case, independent service identities deliver evidence, and a reviewer approves the exact local outbound packet. Filing leaves the case awaiting vendor correspondence. Sending a packet does not manufacture the incoming reply.

The first implemented remedy is the ordinary Twilio Messaging API SLA, dated 2026-04-09, with UTC calendar boundaries and a single continuous incident. An operator-provisioned account binding attests the ordinary subscription, supported generally available service and applicable agreement. A signed status event represents the connector's complete monthly single-incident status statement. A billing event represents its complete period-specific invoice allocation. A customer event independently establishes account impact. These are synthetic local source contracts. A live connector needs an equivalent verified coverage attestation before using them.

## Server integration

Construct CorrespondenceDesk(path, clock=None, active_resolver=None) using the application database. The default clock is current UTC. Tests can inject an aware clock.

Call these methods only during operator-controlled provisioning.

~~~python
desk.provision(
    tenant="bears", account="account-71", vendor="Twilio",
    contract="agreement-X", service="Twilio Messaging API",
    component="api-east", region="east",
)
desk.bind_sender("bears", "account-71", "status", "status-fixture")
desk.bind_sender("bears", "account-71", "customer", "customer-fixture")
desk.bind_sender("bears", "account-71", "billing", "billing-fixture")
desk.bind_sender("bears", "account-71", "vendor", "vendor-fixture")
~~~

The server separately provisions random HMAC secrets for the four named service identities. Source permissions are checked by tenant, account and authenticated subject. A source cannot act as another source on that account. Neither the HTTP request nor an unsigned document chooses the sender or tenant.

Mount make_correspondence_router(desk, actor, reviewer, check_write, service). The actor dependency authenticates a read session. The reviewer dependency authenticates each consequential reviewer action. The service dependency verifies a HMAC over the application instance, origin, exact path/body, timestamp and nonce, and returns a service principal. The service identity has role service. The server middleware supplies body-size, origin and action-header checks. There is no sender-creation endpoint or bearer fallback.

The server security helper uptime.auth_client.service_headers supplies request proof headers. Delivery retries use a fresh transport nonce with the original event ID and content. The persisted event receipt survives process restart, while an old process's HMAC proof cannot authenticate to a new process.

## Request contract

All models reject extra fields. Money inputs are strings. No request accepts a claimable amount, eligibility outcome, sender identity, approval, tenant ID or received timestamp.

POST /api/correspondence/claims requires a reviewer and this body.

~~~json
{
  "claim_id": "inbox-case-19",
  "scope": {
    "account": "account-71",
    "vendor": "Twilio",
    "contract": "agreement-X",
    "service": "Twilio Messaging API",
    "component": "api-east",
    "invoice": "oct-invoice",
    "incident": "evt-411",
    "currency": "USD",
    "month": "2026-10",
    "region": "east"
  }
}
~~~

GET /api/correspondence/claims and GET /api/correspondence/claims/{claim_id} return tenant-scoped workbench views. The same methods are available as desk.cases(principal) and desk.case(principal, claim_id).

POST /api/correspondence/claims/{claim_id}/events requires the authenticated, allowlisted source. Its body contains event_id, the complete identical scope, and one body object. Timestamp strings require explicit UTC offsets. The following body variants are supported.

| Kind | Source | Required fields |
| --- | --- | --- |
| status | status | start, end |
| impact | customer | start, end, boolean affected, exclusion equal to none, unknown or customer |
| component | customer | start, end, component_id |
| notice | customer | start, end, issued_at |
| invoice | billing | lines, an array of {id, kind, amount} |
| message | vendor | receipt_id, natural-language text |

Invoice kinds are affected_api, unaffected_api, carrier, tax and third_party. A line inherits its authenticated invoice envelope. It can repeat any scope field explicitly, but a contradiction blocks eligibility. A component document needs its actual component identity. An artifact digest alone cannot establish that fact.

A message must reference the latest local submission receipt. Vendor text produces a bounded reason proposal and source span. Receipt timing, independent customer evidence and deterministic financial evaluation govern the resulting transition. Unrecognized, contradictory, conditional, injected or unsupported language goes to review. Raw vendor text is retained as untrusted incoming evidence. It never enters an outbound packet.

Delivery returns only event_id, digest and received_at. The sender receives no customer case view. The server records received_at and known_at when evidence enters the claim's knowledge record. A maintenance notice's issued_at can be historical while its knowledge timestamp is later. A known timely notice blocks original filing. A notice acquired after a maintenance reply can justify accepting that denial without sending another packet.

POST /api/correspondence/claims/{claim_id}/actions/{action} accepts {}. Actions are approve-claim, submit-claim, approve-response and submit-response. Render the case's offered actions. A newly acquired component record or an original receipt that contradicts a time-bar reply can support one reviewer-approved response after a 24-hour cooldown. Follow-ups remain within the configured filing window as a local conservative policy. The code does not represent this policy as a contractual appeal deadline.

## Approval and duplicate boundaries

The submitted packet includes scoped identifiers, exact contractual amount, applicable agreement/version, cutoff, terms digest and allowed evidence digests. It excludes raw incoming bodies, annotations and vendor text. A change in evidence, active publication or applicable remedy binding requires fresh approval. Contractual sub-cent estimates stay exact. The simulator abstains from settling a sub-cent result because no monetary rounding rule is assumed.

The reserve_claim helper in uptime.claim_identity uses the caller's transaction to reserve the monthly business obligation across routes. Its key uses tenant, canonical vendor/account, governing agreement ID and version, service, month and remedy. Invoice, incident, component and customer-facing case IDs cannot create another initial filing. For the implemented Twilio branch, governing identity is twilio-apis at 2026-04-09, independently of the customer contract reference. Exact retries return the original reservation. A route/case alias fails before a packet reaches a simulator. A supplement names the original receipt and preserves its scope. Persisted historical filings must be backfilled into this shared registry before enabling a second route over a pre-V4 database.

## Active remedy extension

Other vendors return UNSUPPORTED_RULE unless a trusted server resolver supplies ActiveRemedy. The resolver must re-read a server-persisted ACTIVE publication and its scoped evaluation on every approval or send. It supplies tenant, exact scope, independently recomputed evidence digest, publication version, governing agreement_id, filing cutoff and cited EvaluationResult.

The inbox checks these bindings and uses the supplied remedy cutoff. It never applies the Twilio threshold, rate or maintenance rule to another vendor. This hook is an integration boundary. It is not evidence that a second vendor's correspondence adjudication has been implemented.

## Independent verification

The oracle.json file was committed before the inbox implementation. It specifies objective outcomes and amounts. The vendor_record.json file contains a separate synthetic account record and independently fixed allowed attachment digests. The isolated correspondence_vendor.adjudicate function receives only an outbound packet and that private record. It does not read the claimant store or test oracle. A separately authenticated vendor sender delivers its natural-language result.

Run the regression suite with the project's supported interpreter.

~~~sh
python -m pytest -q tests/test_correspondence.py tests/test_correspondence_api.py tests/test_claim_identity.py
~~~

The tests cover known and later maintenance, independently delivered component cures, ambiguous and hostile text, false time-bar replies, partial awards, exact sub-cent amounts, wrong account/component/invoice scope, contradictory evidence, duplicate content and delivery IDs, concurrent filing, cross-route aliases, restart, observation-only policy and active-publication invalidation. The API tests inject trusted dependencies. Full request-HMAC verification belongs to the integrated server security suite.
