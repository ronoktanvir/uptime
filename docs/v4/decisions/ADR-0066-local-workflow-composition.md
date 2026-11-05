# ADR 66 — isolated workflow composition and Local ledger

Root approved the smaller architecture after reading the actual [66 review](reviews/66-local-workflow-composition.json), session `da481892-dcc3-41b4-a884-8a73a045219f`, and [66a review](reviews/66a-minimal-existing-authority-composition.json), session `e6b1ac38-cedf-4da1-8782-3362425c4a76`. The packets and all earlier alternatives remain preserved.

## Decision and rejected alternatives

Use a fresh, separately owned database bound to the existing `bears` replay/rehearsal authority. Harborline Analytics is the buyer, Northwind Cloud the vendor, and CalyxQuay a separate onboarding adapter. Internal tenant identity does not masquerade as a customer name. The configured workflow selects exact account, vendor, agreement, source and record identities; its writes enforce the same set. It cannot select or modify the real Ramp workspace.

Reuse existing authenticated service functions for one operation per action. The generic workflow endpoint receives the current exact reviewer proof. Source arrivals use distinct local fixture keys and the existing signature, grant, nonce, role and scope verifier. This is actual service execution with fictional inputs, not an independently observed external source. No shared auth widening, automatic human enrollment, custom-tenant bypass, queued self-HTTP worker or alternate calculation engine is introduced.

The actual principal remains `scripted-test-reviewer` in audit records. Dana Reyes is only a fictional display alias; the detail projection includes both the principal and `SCRIPTED_REVIEWER` kind. A click does not create ACTUAL_HUMAN evidence. No blanket additional permission is required for this user-authorized local engineering. Native provider writes, actual commercial authorization and external financial effects remain outside this decision.

Root rejected the adviser's suggested fixture-specific signature-freshness policy. Runtime fictional source keys sign ordinary current-wall-time envelopes. The existing freshness, nonce and origin checks remain unchanged. The domain event clock is limited to the separately bound replay/rehearsal database and existing clock injection; authentication still uses the real clock. Neither clock, provider, database nor credentials can be selected by request parameters.

A read-only static replay was cheaper but would not satisfy the requested state, idempotency and ledger execution. The original custom-tenant/queued design added unnecessary issuer simulation, auth scope and recovery complexity. The retained workflow intent and provider records are explicit new infrastructure, not hidden proof flags.

## Financial boundary and recovery

The optional connection is named **Local ledger** and uses `local-ledger:<UUID>` identifiers. It is allowed only for the isolated replay/rehearsal workspace; it cannot coexist with native provider configuration. Records retain `DETERMINISTIC_REPLAY`, never native Ramp provenance.

The existing Workbench derives the exact award, credit and application plan from authenticated claim/evidence records. Existing authority checks and AllocationLedger SQL scope, currency, date and capacity checks run first. A new optional confirmation callback executes after those SQL checks inside the uncommitted financial transaction: write the local provider record to its separate database, read the same UUID back, compare its canonical payload and digest, and then commit. A failed or mismatched readback rolls back financial intake. A provider write surviving a crash is reused under the same identity; recovery recomputes the plan from domain records and never treats provider data as new entitlement.

Post and apply remain separate operations with separate current bounds. The March price discrepancy retains its own identity and is never subtracted as an unawarded credit. Unknown usage yields null entitlement. The projection displays the allocation ledger's balance and stage amounts without adding successive stages.

Workflow action identity must bind the database instance UUID, package/source digest, exact scope, operation, current packet/state and monotonic domain revision. A completed action returns current authoritative records without executing the next action. A stale intent after rollback/reactivation or database reset is refused. An interrupted intent remains identifiable for exact recovery; an ambiguous outcome is not converted to completion.

## Middleware and service checks

The outer workflow route retains the server's exact loopback origin, bounded body, CSRF/action headers, write serialization, reviewer challenge consumption and workspace policy check. Shared CorrespondenceDesk and Workbench calls retain their role, tenant, packet, evidence, mandate and financial invariants. Generated local source envelopes additionally traverse `Authority.service` and its SourceGrant checks before inbox intake; no ServicePrincipal is fabricated. Existing native dispatch separately refuses rehearsal, and startup rejects native configuration alongside this local connection. These boundaries require integration tests; composition alone is not proof that they are present.

## Validation and limits

The first provider increment `24dbed1` passes 15 focused controls: exact UUID readback, repeated posting/application, restart after write/readback failure, wrong response identity/tenant/hash, conflicting provider payload, currency/scope/over-cap validation before provider side effects, preserved bill capacity, and wrong mode/tenant/instance rejection. Full workflow and socket verification remain pending until the source-bound stepped-fee join and setup are integrated. Record final results in the linked workstream test ledger.

This walkthrough cannot establish real governing customer terms, actual human promotion, independent external credit evidence, or native Ramp write/readback/application. Their historical gates remain separate. No human accuracy, independent-review or screenshot truthfulness study is inferred from scripted test success.

Rollback removes only the configured local workspace/provider files after preserving its receipts. Existing customer workspaces, V3 history, private corpora and live proof records are untouched.

## Completed composition and Decision68 correction

The implemented service path uses an application-owned FeeRegistry and trusted event clock. Current catalog controls, approval/activation, saved case projections and correspondence re-resolve the already authenticated invoice evidence. Fee registry closure removes current monetary estimates/actions while immutable history remains. The exact fee context digest enters the correspondence approval version; the governing pricing version remains a separate field.

Decision68 selects a separate April1 invoice instead of applying to the existing March invoice. The allocation date guard is unchanged. The fixed receive-next-invoice intent advances monotonically to the authored availability, creates the exact April source scope, and receives the invoice, an invoice-detail artifact containing the opening capacity, and a linked billing verification under distinct customer/billing keys. Exact hashes, roles, full scope, link, chronology, original source and unchanged-SLA citation are checked before capacity intake. Partial source writes and capacity intake resume under the same intent and immutable IDs. No April metadata is exposed by the workflow before availability.

The ledger uses the original awarded SLA eligibility version because the cited authored amendment explicitly preserves the SLA/remedy; it separately retains April's pricing amendment version, invoice/source hash and original issue/service/known dates. April11000 minus applied2400 leaves8600. March's1000 exposure is unresolved and receives no allocation. This bounded case does not define a general legal meaning for every use of “future invoice.”

The fixture setup now creates a0600 browser P-256 JWK derived from the existing rehearsal key. Its marker and actual principal remain scripted-test-reviewer. Dana Reyes remains only a display alias; no human account is enrolled. Setup finishes before serving requests, and the public extraction opt-in is restored immediately after the accepted CalyxQuay installation.

Final focused evidence:86 passing tests, plus11 actual socket actions with duplicate-response and separate GET readback equality. The public socket receipt is retained under `docs/v4/validation/northwind/final-socket.json`. Root performs the complete integration suite and browser verification. These results establish local service/ledger execution and recovery, not real-party authority, actual provider issuance, external model generalization or native Ramp recovery.
