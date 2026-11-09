# Document and evidence support matrix

**Checkpoint:** `work/evidence-custody-90` at `a924aae`, November 9, 2026. Workstream W5, evidence and source custody.

**This describes what the code supports today. It is not the agreed matrix.** Team decision D07 owns which formats, calendars, currencies and evidence sources the first release requires. Until D07 is recorded, nothing below authorizes a claim of general contract ingestion. "Supported" means an ordinary application path with tests; "bounded" means one family or fixture; "absent" means refused or not implemented.

## 1. Contract documents

| Input | Entry path | Custody kept | Clause location | Status |
|:---|:---|:---|:---|:---|
| UTF-8 text inside Document JSON | `POST /api/vendors/{id}/candidates` → `vendor_registry.install` | Exact text (≤50,000 characters) in the immutable artifact row; SHA-256 of the UTF-8 text; receipt time | Character offsets and exact quotes, verified against the text when compiled; later checks recompute the whole-text hash | **Supported** for the monthly-availability, completed-step and resource-month families. Their grammar is finite; unsupported prose refuses. No separate document-version field; the resource family can record a "Version X" heading. |
| Same document through a public model proposal job | `public_proposal_jobs`, `vendor_model_jobs` | Request ≤80,000 bytes; context hash binds document and text hash; raw provider output retained | Model spans must match the stored text exactly | **Supported as a proposal only.** Human review of the interpretation is still required; customer documents are not sent (D10). |
| Typed pricing agreement and amendments | `pricing.py`, `pricing_terms.compile_fixed_monthly` | Text hash and `Citation(document, version, section, uri)` | Section names; fixed-monthly schedule keeps offsets | **Bounded.** No HTTP intake. Amendments form a linear chain with strictly increasing effective dates; a line crossing an amendment date refuses. |
| Signed Ramp terms packet | `ramp_terms_store.install` | **Original bytes** on disk, named and verified by SHA-256 (8 MiB each, 32 MiB total); version and contract hash | Rates are signed attestations, not extracted text | **Bounded** to operator-attested packets. |
| PDF | Legacy Atlassian `onboarding_extract` only (`pdftotext -layout`, fixed URL) | Byte and text hashes only; neither bytes nor extracted text are kept | Hand-labelled sections; **no page numbers** | **Absent as general ingestion.** Numbers are compared with a hand-authored gold record. |
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

**Rejected, not quarantined.** Every refusal raises inside the intake transaction, so nothing is stored and no refusal is logged. A refusal audit stream and a supersede path for an already-stored mistaken record are requested from W0 and W4 (F7).

## 3. Acceptance conditions

| Condition | Current behavior |
|:---|:---|
| Wrong customer | Signed channel refuses envelope and nested mismatches. Embedded/HMAC channels store foreign nested rows (F2). |
| Wrong period | Signed channel refuses records wholly outside the month (decision 91). Embedded/HMAC channels store them and block the claim (F1). A short record within 14 hours of the boundary is admitted and left to the evaluator. |
| Stale | The public status snapshot is `stale` after 24 hours and `gap` if collected after the audit clock. A complete report observed before its period ended is refused. Signed evidence has **no maximum age**; a per-kind freshness policy for mutable records (payment state, refunds, account conditions) needs D07. |
| Tampered | Signatures cover exact bytes; declared content digests are recomputed; public snapshots verify raw and per-observation hashes; Northwind fixtures verify file hashes and specimen signatures. |
| Duplicated | Same event ID is idempotent; identical content under a new ID is recorded as an alias; overlapping intervals are merged as a union and cannot inflate downtime. |
| Contradictory | One record per kind; a second becomes insufficient evidence. Status and impact must agree on the interval. Later contradictory evidence moves an awarded claim to human review. Customer and provider telemetry are combined by intersection, so disagreement cannot add downtime. |
| Incomplete / missing intervals | Generic monthly, resource, aggregate service-month, dual-telemetry and Northwind paths require an explicit complete-period attestation or explicit negative finding; otherwise insufficient evidence. **Exception: the Twilio ordinary correspondence profile** (F3). |

## 4. Public outage versus customer impact

A public status incident never produces an entitlement by itself. The public snapshot is display-only (`standalone_entitlement: False`, "customer impact unverified"); the Twilio evaluator requires an affected-customer mapping; resource evaluation requires account-specific evidence; the correspondence profile requires separately signed status, customer impact and billing records. No path was found where a public incident alone yields `ELIGIBLE`. The Twilio profile's trace names `https://status.twilio.com` as the status origin without verifying that the enrolled source is that page (F8).

## 5. Findings outside W5 ownership

Reproduced findings are in the [receipt](evidence/evidence-custody-90/findings-91.json); the others cite code.

| ID | Finding | Owner | Decision dependency |
|:---|:---|:---|:---|
| F1 | Embedded and HMAC channels store wrong-period records; the one-per-kind desk then reports the correct records as contradictory with no recovery. **Reproduced.** | W4 (`correspondence.py`) | None for applying the decision-91 rule at the desk |
| F2 | Embedded and HMAC channels store nested rows naming another account; evaluation is then blocked. **Reproduced**; also asserted by existing `test_mismatched_fee_and_component_prevent_further_packet`. | W4 | None |
| F3 | The Twilio ordinary profile builds month coverage from one signed per-incident status record. A two-minute incident returns `INELIGIBLE` without the explicit complete-month `coverage` report, and the trace presents the status digest as month coverage. **Reproduced.** Missing evidence becomes ineligibility, and an eligible amount is a lower bound presented as exact. | W4 / W2 (`correspondence_rules.py`) | D07 (required evidence); a contract-semantics decision, not a routine fix |
| F4 | A private filing-amendment override carries no agreement, effective date or source hash; it applies across the whole overlay interval. | W3 (`vendor_terms.py`) | D07 |
| F5 | A resource-month manifest without an agreement name, and with no precedence clause, accepts an overlay for any agreement name. | W3 | May intersect D03 |
| F6 | `GoverningTerms.evidence_sha256` is only format-checked; nothing verifies it against stored evidence. | W3 | None |
| F7 | No refusal audit stream; no authorized supersede path for a mistaken stored record. | W0 (`auth.py`, storage) with W4 | None |
| F8 | The status origin in the Twilio trace is asserted, not verified against the enrolled source. | W2 / W4 | D07 (connector choice) |
| F9 | The legacy Atlassian PDF path keeps no original bytes, extracted text or page map. | W3 | D07 (if PDF becomes a supported format) |

## 6. Assignment items that wait on a team decision

| Item | What is ready | What needs a decision |
|:---|:---|:---|
| Agreed support matrix | This current-state matrix | **D07**: the team's required formats, calendars, currencies and evidence sources |
| PDF, OCR and other document formats | Exact-text custody and offset verification for the supported text path | **D07** to select formats; **D10** before any private document reaches a model. Building PDF/OCR intake now would be speculative scope. |
| Selected evidence connector | Signed enrollment, rotation, revocation, scope and temporal checks | **D07** to choose one real evidence source; **D11** for who enrolls and holds source keys outside this local machine |
| Freshness policy for signed evidence | Snapshot staleness; completion chronology | **D07** per-kind maximum age for mutable records |
| Dispute delivery channel | Authenticated signed intake for vendor messages and receipts | **D08** for the real channel, delivery receipts and authorization |
| Implicit Twilio completeness (F3) | Reproduction and recommendation: require the complete-month report before `INELIGIBLE` or an exact amount | **D07** and the profile owner; changes many existing dispute tests |

Source signatures attribute a record to an enrolled key. They do not establish that the record is true, that the key belongs to the named organization, or that every underlying claim is complete.
