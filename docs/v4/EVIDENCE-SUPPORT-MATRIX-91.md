# Document and evidence support matrix

**Checkpoint:** `work/evidence-custody-90` at `9eafdf5`, November 9, 2026. Workstream W5, evidence and source custody.

**Agreed scope (D07, decided November 9 by Ronok; relayed from his overview session and recorded by the integration owner): narrow published matrix.** The first release covers exact source imports plus customer overlays, USD only and calendar-month periods. Taxes, other currencies, partial periods, ambiguous amendments and business-calendar rules return unsupported. One real evidence source is onboarded end to end. There is no PDF intake. The tables below say what the code does today against that scope. "Supported" means an ordinary application path with tests; "bounded" means one family or fixture; "absent" means refused or not implemented. This document covers documents and evidence. Whether each financial engine returns *unsupported* for taxes, currencies, partial periods, ambiguous amendments and business calendars belongs to the engine owners (W2, W3) and is not verified here.

| D07 element | Current state (W5 view) |
|:---|:---|
| Exact source imports | Exact UTF-8 text with verified character-offset citations (section 1). |
| Customer overlays | Supported, with binding gaps F4–F6 accepted by W3 for one batched semantics revision. |
| One currency, calendar months | Evidence intake checks the granted `YYYY-MM` month (decision 91); currency equality is checked at the grant. |
| No PDF intake | Confirmed: no general PDF path; the legacy Atlassian extractor stays a separate legacy lab (F9 out of scope). |
| One real evidence source | Twilio's public status page through the ordinary enrollment tools and signed intake (decision 91a, section 7). **Intake verified with a live public capture; release gate pending**, because the ordinary launcher's release gate is unsatisfied and the rehearsal workspace was harness-hosted. |

## 1. Contract documents

| Input | Entry path | Custody kept | Clause location | Status |
|:---|:---|:---|:---|:---|
| UTF-8 text inside Document JSON | `POST /api/vendors/{id}/candidates` → `vendor_registry.install` | Exact text (≤50,000 characters) in the immutable artifact row; SHA-256 of the UTF-8 text; receipt time | Character offsets and exact quotes, verified against the text when compiled; later checks recompute the whole-text hash. `scripts/audit_document_custody.py` re-slices every stored citation read-only: 77 of 77 citations across 5 adapter versions in the Northwind presentation and CalyxQuay review workspaces trace exactly ([receipt](evidence/evidence-custody-90/document-custody-91.json)) | **Supported** for the monthly-availability, completed-step and resource-month families. Their grammar is finite; unsupported prose refuses. No separate document-version field; the resource family can record a "Version X" heading. |
| Same document through a public model proposal job | `public_proposal_jobs`, `vendor_model_jobs` | Request ≤80,000 bytes; context hash binds document and text hash; raw provider output retained | Model spans must match the stored text exactly | **Supported as a proposal only.** Human review of the interpretation is still required; customer documents are not sent (D10). |
| Typed pricing agreement and amendments | `pricing.py`, `pricing_terms.compile_fixed_monthly` | Text hash and `Citation(document, version, section, uri)` | Section names; fixed-monthly schedule keeps offsets | **Bounded.** No HTTP intake. Amendments form a linear chain with strictly increasing effective dates; a line crossing an amendment date refuses. |
| Signed Ramp terms packet | `ramp_terms_store.install` | **Original bytes** on disk, named and verified by SHA-256 (8 MiB each, 32 MiB total); version and contract hash | Rates are signed attestations, not extracted text | **Bounded** to operator-attested packets. |
| PDF | Legacy Atlassian `onboarding_extract` only (`pdftotext -layout`, fixed URL) | Byte and text hashes only; neither bytes nor extracted text are kept | Hand-labelled sections; **no page numbers** | **Out of first-release scope (D07).** Not general ingestion; numbers are compared with a hand-authored gold record. |
| HTML | Legacy Atlassian support article parser | Hashes only | None | **Absent as general ingestion.** |
| Scanned image / OCR, DOCX, email, spreadsheet | None | — | — | **Absent.** No extraction-uncertainty representation exists, so no OCR number can be presented as established. |

Amendment and overlay binding today: an overlay must name a supported product and plan, USD, and an effective interval that overlaps the document; each evaluated month must lie inside both. The monthly family requires the overlay agreement to equal the document agreement. Gaps are listed in section 5 (F4–F6).

## 2. Operational evidence: signed source channel

Each source is enrolled offline with an Ed25519 key, one role (`status`, `customer`, `billing`, `vendor`) and one exact scope (account, vendor, contract, service, component, invoice, incident, currency, month, region). [Source intake](SOURCE-INTAKE.md) describes provisioning.

| Check | Where | Signed channel | Embedded desk / HMAC fixture channel |
|:---|:---|:---|:---|
| Exact bytes, timestamp ±60 s, single-use nonce, instance, origin, tenant, mode | `auth.py` | Refused (403) | HMAC: same transport checks |
| Envelope scope equals the grant; role matches kind | `source_config.event_in_scope` | Refused (403) | Desk compares envelope scope and role |
| Nested rows name the same account, resource, month, currency | `event_in_scope` | Refused (403) | **Stored**; the evaluator returns insufficient evidence (F2) |
| Measured time inside the granted month (**decision 91**) | `evidence_applicability.temporal_refusal` | Refused (403) before storage | **Stored**; the claim is then blocked as contradictory (F1) |
| Complete report observed before its interval ends (**decision 91**) | same | Refused (403) | Desk refuses this for resource reports only |
| Completed intervals only; no future observation, notice or receipt | `correspondence.receive`, `validate_arrival` | Refused (409) | Refused (409) |
| Declared content digests (aggregate records, artifacts, reviewed terms) | `validate_arrival` | Refused (409) | Refused (409) |
| Same event ID with different content | `correspondence.receive` | Refused (409); identical retry returns the original receipt | Same |
| Revoked or rotated key; changed grant | `SourceRegistry.lookup` re-reads the protected file per delivery | Refused (403) | Not applicable |

**Rejected, not quarantined.** Every refusal raises inside the intake transaction, so nothing is stored and no refusal is logged. A refusal audit stream (F7a, W0) and a supersede path for an already-stored mistaken record (F7b, W4) are accepted as open items, not yet implemented.

## 3. Acceptance conditions

Signed-path acceptance on the merged integration head `23805c9`: 219 passed, 1 warning, including seven dedicated controls in `tests/test_evidence_acceptance_91.py` ([receipt](evidence/evidence-custody-90/acceptance-merged-91.json)).

| Condition | Current behavior |
|:---|:---|
| Wrong customer | Signed channel refuses envelope and nested mismatches. Embedded/HMAC channels store foreign nested rows (F2). |
| Wrong period | Signed channel refuses records wholly outside the month (decision 91). Embedded/HMAC channels store them and block the claim (F1). A short record within 14 hours of the boundary is admitted and left to the evaluator. |
| Stale | The public status snapshot is `stale` after 24 hours and `gap` if collected after the audit clock. A complete report observed before its period ended is refused. Signed records are dated observations and have no intake maximum age; current-state freshness belongs to the evaluator that relies on it (section 6). |
| Tampered | Signatures cover exact bytes; declared content digests are recomputed; public snapshots verify raw and per-observation hashes; Northwind fixtures verify file hashes and specimen signatures. |
| Duplicated | Same event ID is idempotent; identical content under a new ID is recorded as an alias; overlapping intervals are merged as a union and cannot inflate downtime. |
| Contradictory | One record per kind; a second becomes insufficient evidence. Status and impact must agree on the interval. Later contradictory evidence moves an awarded claim to human review. Customer and provider telemetry are combined by intersection, so disagreement cannot add downtime. |
| Incomplete / missing intervals | Generic monthly, resource, aggregate service-month, dual-telemetry and Northwind paths require an explicit complete-period attestation or explicit negative finding; otherwise insufficient evidence. **Exception: the Twilio ordinary correspondence profile** (F3). |

## 4. Public outage versus customer impact

A public status incident never produces an entitlement by itself. The public snapshot is display-only (`standalone_entitlement: False`, "customer impact unverified"); the Twilio evaluator requires an affected-customer mapping; resource evaluation requires account-specific evidence; the correspondence profile requires separately signed status, customer impact and billing records. No path was found where a public incident alone yields `ELIGIBLE`. The Twilio profile's trace names `https://status.twilio.com` as the status origin without verifying that the enrolled source is that page (F8).

## 5. Findings outside W5 ownership

Reproduced findings are in the [receipt](evidence/evidence-custody-90/findings-91.json); the others cite code.

Owner responses are as reported by each owner's session or recorded in the integration owner's blocker register on November 9; they are not verified implementations. "Not yet answered" means the request was sent and no disposition has arrived.

| ID | Finding | Owner | Decision dependency | Owner response |
|:---|:---|:---|:---|:---|
| F1 | Embedded and HMAC channels store wrong-period records; the one-per-kind desk then reports the correct records as contradictory with no recovery. **Reproduced.** | W4 (`correspondence.py`) | None | **Accepted, modified.** The desk will refuse before storage, record a timeline entry and clear any pending approval. It follows the W0 merge of this branch. |
| F2 | Embedded and HMAC channels store nested rows naming another account; evaluation is then blocked. **Reproduced**; also asserted by existing `test_mismatched_fee_and_component_prevent_further_packet`. | W4 | None | **Accepted, modified.** Out-of-scope deliveries go to a separate per-case contradicting-deliveries list, not evidence. They clear approval and move a pending cure or rebuttal to human review. Changed existing tests are to be listed in W4's ledger. |
| F3 | The Twilio ordinary profile builds month coverage from one signed per-incident status record. A two-minute incident returns `INELIGIBLE` without the explicit complete-month `coverage` report, and the trace presents the status digest as month coverage. **Reproduced.** Missing evidence becomes ineligibility, and an eligible amount is a lower bound presented as exact. | W4 / W2 (`correspondence_rules.py`) | D07 (required evidence); a contract-semantics decision, not a routine fix | **Accepted; was blocked on D07, which is now decided (narrow matrix).** Meanwhile the trace names the assumption (`month_coverage_basis = PROVISIONED_SINGLE_INCIDENT_RECORD`). The real public status source never emits a coverage record, so live use of it in this profile depends on this change. |
| F4 | A private filing-amendment override carries no agreement, effective date or source hash; it applies across the whole overlay interval. | W3 (`vendor_terms.py`) | D07 (now decided) | **Accepted** by W3, batched into one semantics revision after D03; interim: install a mid-term addendum as a separately dated slot. |
| F5 | A resource-month manifest without an agreement name, and with no precedence clause, accepts an overlay for any agreement name. | W3, with the D03 identity owner | D03 (decided D03-A) | **Decided by Ronok, November 9: require reviewed binding.** An overlay's agreement must be explicitly bound to its governing document in the reviewed adapter; unbound overlays refuse. agent1 and agent2 batch it with F4/F6 in one `vendor_terms` re-review. |
| F6 | `GoverningTerms.evidence_sha256` is only format-checked; nothing verifies it against stored evidence. | W3 | None | **Accepted**: documented as an operator-supplied reference until verified. |
| F7a | No audit stream of refused intake deliveries. | W0 (`auth.py`) | None | **Accepted as an open W0 item**; not in the current integration. |
| F7b | No authorized withdrawal or supersede path for a mistaken stored record. | W4 (its inbox tables) | D06/D07 (who may retract a signed record) | **Accepted as a design item, blocked.** Proposed shape: a source-signed retraction that references the original event, keeps history and voids approvals. |
| F8 | The status origin in the Twilio trace is asserted, not verified against the enrolled source. | W2 / W4 | D07 (connector choice) | **Accepted** as an honest label: `status_origin` names the enrolled subject and grant; the profile URL becomes `profile_assumed_origin`. |
| F9 | The legacy Atlassian PDF path keeps no original bytes, extracted text or page map. | W3 | D07 (if PDF becomes a supported format) | **Out of scope:** D07 excludes PDF intake from the first release. |

On the signed channel the decision-91 grant refuses out-of-scope records with HTTP 403 before the desk, so the W4 contradicting-deliveries list covers only the embedded and HMAC channels. A per-case trace of signed-channel refusals depends on F7a.

## 6. Assignment items and decision status

| Item | State | Remaining dependency |
|:---|:---|:---|
| Agreed support matrix | This document, aligned with D07 (header table) | Engine owners verify the unsupported outcomes for taxes, currencies, partial periods, ambiguous amendments and business calendars |
| Document formats | Exact UTF-8 text with verified offsets. PDF, OCR and other formats are outside the first release (D07) | None for the first release. D10 (decided): only public data goes to Claude; private overlays and customer captures stay local. Both decision-91 critique packets contained only public or authored data |
| Real evidence source | Twilio public status page, decision 91a. Live capture of November 9 delivered through the enrollment tools, the signed CLI and HTTP intake; retry idempotent; claim stays insufficient without customer impact. [Receipt](evidence/evidence-custody-90/public-status-live-91a.json) | Launch path: the ordinary launcher needs the release gate. Live claim use also depends on the W4 F3 change. Whether a harness-hosted run counts toward D07 is Ronok's call |
| Freshness | Public status: 24 hours at delivery; complete reports cannot predate their period end | W5 position, open to Ronok: a signed record is a dated observation and intake does not age it out. Staleness matters only where an evaluator relies on *current* state (still unpaid, not refunded, account still in good standing, subscription still active); that evaluator should require an observation no older than its own decision window and otherwise return insufficient evidence. D07 set no window, so none is invented here; the owners are W2/W4 (billing and account state) and W3 (subscription records) |
| Dispute delivery channel | Authenticated signed intake for vendor messages and receipts | **D08** (pending) |
| Retraction of a signed record (F7b) | W4 design: source-signed retraction that keeps history and voids approvals | Must fit the **D06** action matrix (owner W0, not yet written) |

## 7. The real evidence source (decision 91a)

The status source maps one verified public snapshot and one operator-selected incident to one signed `status` record for an exact enrolled grant. It refuses another origin, a snapshot older than 24 hours or from the future, another vendor, another incident or a component the incident does not name, an unresolved incident, a missing published start (creation time is never substituted), a non-positive interval, a resolution after observation, and the decision-91 month rule. Component matching uses the feed's stable component IDs, never names. Event identity follows the canonical incident hash, so separate fetches of an unchanged incident share one identity and a public edit becomes a distinct record that intake surfaces as a contradiction for review. The record carries no public label, no customer impact and no coverage claim. The signer is the local operator who fetched the page, not Twilio. The recent-incident feed is truncated, so older months may be unanswerable; that refuses as "not in this snapshot". Clocks: the operator's machine sets collection and delivery times; the server checks its own clock within 60 seconds of the signature.

Source signatures attribute a record to an enrolled key. They do not establish that the record is true, that the key belongs to the named organization, or that every underlying claim is complete.
