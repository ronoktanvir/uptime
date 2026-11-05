# Uptime V4 on Ramp

Ramp owns the business, vendor, purchase order, bill, approval, card transaction, native discussion and applied-credit records. Uptime owns the interpretation of a contract, its evidence, the dispute and its audit trail. The joining key is a typed, scoped provider identifier. A matching merchant name, a vendor email or an equal dollar amount cannot establish that association.

## From the invoice to the approver

1. The operator obtains sandbox-only OAuth client credentials from their protected local store. A read of the current business pins this installation. Resource-specific tokens, bounded pagination and separately labeled truncation preserve the scope and cost of the read.
2. The importer minimizes records, verifies the snapshot checksum and stores immutable capture history under the tenant-business binding. A pending import can resume after interruption. The primary worklist starts from this capture. Provider deep links appear only when returned by Ramp. The offline package replays a verified historical capture.
3. A bare invoice establishes status and spend. Pricing requires signed terms, an effective amendment chain, scoped line/service/quantity evidence and a defined economic basis. The operator may install an independently signed package bound to a particular capture. Each read revalidates the signed content and retained evidence. A synthetic overlay and the factual invoice have separate classifications. SLA claims require time, service, usage, fee and cause evidence beyond the bill.
4. A positive result can prepare a finding for a specific native thread. The bill comment transport pins a single business, bill, finding and exact HTTP payload. A named reviewer and separately issued effect-specific mandate authorize the action. The provider is reread at the final write boundary. The outbox reconciles an uncertain transport result against the same thread before another delivery. A note informs an approver. Only a configured Ramp workflow step can affect approval routing.
5. A verified award, a native credit and a native bill application have different identifiers and lifecycles. Independent scopes and signatures bind the award and allocation. Uptime checks reciprocal amounts, currency, remaining capacity and time. Reconciliation holds ambiguous or one-sided matches for review. The sandbox supplies no real-world cash measurement.

[Provider feasibility](RAMP-FEASIBILITY.md) · [Record reader](RAMP-RECORDS.md) · [Economic bindings](RAMP-PRICE-EVIDENCE.md) · [Native review](NATIVE-OPERATOR.md) · [Credits](RAMP-CREDIT-SYNC.md) · [Award attribution](RAMP-ATTRIBUTION.md)

## Evidence and authority

The companion offers a vendor adapter registry and a correspondence inbox. Public document bytes and their citations bind model propositions to typed, enumerated rules. A private customer overlay specifies applicability. The compiler checks coverage, case controls and durable evaluator-version hashes. Accepted candidates start in shadow. A separate reviewer can promote and roll back a version. Promotion tests include independent expectations. A generated candidate never executes model-produced code.

Inbound correspondence is untrusted even when a trusted transport delivers it. A registered source signs the active tenant/account/contract/service/region/invoice/incident scope. Time, causal evidence, eligible fees and filing/supplement facts control the deterministic response and permitted action. Source roles and reviewer authority are separate. Unknown text can legitimately require escalation. A provider reply alone cannot mint a monetary award. The counterparty simulator operates on contract inputs and submitted evidence, and its output carries simulated provenance.

The current deployment is a single-host loopback application with scoped SQLite state and separately enrolled public keys. An organizational Internet deployment would additionally need customer OAuth installation, managed identity, durable hosting and backup, verified domain-to-vendor enrollment, and externally owned signing keys. The implementation provides a local investigation console and operator interfaces. It has no production Ramp credential path.

[Source intake](SOURCE-INTAKE.md) · [Adapter operation](../vendor-onboarding.md) · [Reviewer mandates](REVIEWER-MANDATES.md) · [Decision index](decisions/INDEX.md)
