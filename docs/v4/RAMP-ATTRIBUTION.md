# Verified award attribution is an observation, not a settlement

`uptime/ramp_award_attribution.py` adds a complementary, offline observation
journal. It does not extend `Source`, instantiate `AllocationLedger`, write its
tables, create an award in that ledger, or call a provider. The existing ledger
accepts only `SIMULATED_VENDOR` awards. Its simulated financial amounts remain
separate. A credit already recorded there is reserved against attribution here.

The output answers: **which independently confirmed award amounts have an exact,
human-approved association with this observed Ramp credit and its bill usage?**
`RAMP_APPLIED_ATTRIBUTED` means a native payable application observed in Ramp,
not independent bank settlement or realized cash. `actual_recovered_cash` and
the compatibility field `actual_recovery` are always null. Production is not
supported by this version.

## Evidence consulted and limits of the current demonstration

This implementation consulted the genuine sanitized packets and saved Opus 5.5
reviews in the integration worktree, without making another external call:

| Artifact under `docs/v4/decisions/` | SHA-256 |
| --- | --- |
| `packets/34-ramp-credit-attribution.md` | `b23869b46492b951bab1fd7e6338e7ec5131d1f9c8505e4a048beb59b49d4b35` |
| `reviews/34-ramp-credit-attribution.json` | `473763250909c294eba4a911f16a0ab53b4d7326958f2ea1ec558b69bd09a54c` |
| `packets/40-provider-confirmed-awards.md` | `b80147597c98e19cbc0b03357fbef0bd43649a371637376ac2f0703d67d5a68e` |
| `reviews/40-provider-confirmed-awards.json` | `50848caf63868bda78fc51244f467930078b3d12b73a99eaea0b400b5da0d640` |

Both review `packet_sha256` values match the packet bytes. Review 34 is timestamped
2026-11-05T00:20:12.164307Z; review 40 is timestamped
2026-11-05T00:27:36.529561Z. Their conclusions require explicit allocation,
independent source verification, dual control, immutable scope, and no cash claim.
The source baseline is credit-sync commit
`b3b8facdd6011cbdb1b66712d713da060135cbb8`; its later quarantine interface was also
read. The new module has no import dependency on that branch.

Packet 40 reports six sandbox bills and zero vendor credits. The saved
`docs/v4/evidence/ramp-discovery.json` likewise reports a credit sample count of
zero and no next page. These are historical observations from the integration
worktree, not fresh calls by this worker. No affiliated real vendor award was
provided or created. The tests generate all keys, people, claims, awards, and
native-shaped records locally. Even tests exercising `ACTUAL_NATIVE` validate
the trust gates only; they are not genuine financial observations.

The cited packet describes the published API snapshot as read-only for vendor
credits. This module does not depend on that continuing to be true: it has no
provider transport or mutation operation of any kind. No credentials were read,
and no vendor, Ramp, or other external service was contacted for this work.

## Office configuration is the trust root

The office must review and install a public `OfficeConfig` outside the API. There
is deliberately no enrollment endpoint, private-key generation helper, signer,
fixture-to-native promotion, or automatic migration. The optional operator CLI
loads one explicitly named, operator-owned 0600 regular file from an
operator-owned directory that other users cannot write. It rejects symlinks.
The constructor also accepts an already reviewed model for trusted server
composition; **never build that argument from an HTTP request or applicant file**.

The configuration contains an installation ID, exact tenant and Ramp business
UUID, sandbox environment, evidence mode (`ACTUAL_NATIVE` or `MOCK`), a reviewed
document reference/hash, and four separate witness roles:

| Role | Required external review | May sign |
| --- | --- | --- |
| `claim_registrar` | Governing contract/version, beneficiary, commercial account, product, local filing, and exact bill scope from independent retained records | Immutable filed-claim registration and external custody |
| `vendor_verifier` | Actual vendor channel and signer authority; source authenticity and independence from claimant and Ramp | External filing custody and vendor award confirmation |
| `finance_approver` | Named authorized human, finance mandate, exact operator-to-key association, and each proposed financial attribution | Award confirmation and each attribution |
| `ramp_observer` | Custody of genuine authorized GET readbacks, exact sandbox origin and business identity, grants, pagination and detail-read coverage; use mock custody for `MOCK` | Native snapshot observations |

Every witness has a distinct Ed25519 public key, subject, `operator_id`, and
operator-key fingerprint, a validity interval, an association evidence
reference/hash/method, and a source-verification evidence reference/hash/method.
All roles other than the capture witness have exact `ClaimScope` allowlists;
there are no wildcard accounts or beneficiaries. Scopes include native vendor
UUID, vendor name, account, beneficiary, canonical contract/version, product,
service, month, remedy, currency, and native minor-unit conversion rate.

The office must verify the identity association through an established channel,
check key possession independently, retain the source documents, and establish
the person's actual authority to approve this tenant/business. Merely naming a
person, supplying a public key, or possessing a normal reviewer login does not
establish commercial authority. When an `authority_user` table is present,
finance's `operator_id` must also name a current enrolled reviewer and its
`operator_key_sha256` must match that account's enrolled key. An Ed25519 signing
key can differ from the login key; the reviewed association explicitly connects
them. The vendor verifier, registrar, and human approver cannot be the applicant.

Export the existing inbound source identities, including retired keys, into
`OfficeConfig.authority_sources`. Those identities cannot become witnesses here.
The module also rechecks `authority_source(subject, public_key)` if present, and
the existing `source_key_history` allowlist/history used by the newer authority
implementation. An unknown `authority_source` schema fails closed. Neither
`SourceGrant`, a service principal, a prior reviewer mandate, a source label,
nor a prior award creates this new authority. Existing workspace mode, tenant,
and native business bindings are checked when those tables exist.

Ed25519 proves who signed exact bytes. It cannot prove that a portal is genuine,
that two named people are independent, or that a signer verified a document.
Those facts are the office's documented trust decisions. A malicious office or
compromised authorized witness remains outside this prototype's protection.
The application stores references and hashes, not private keys or raw vendor
correspondence. Keep the SQLite DB protected; its triggers are application
immutability, not tamper resistance against its filesystem owner.

All evidence witnesses' grant validity is rechecked for new attribution and its
current summary; an expired historical grant cannot authorize another binding.
The exact office configuration is pinned in the store. Changing keys, roles,
scopes, installation, or evidence mode fails closed, even after a restart.
There is no reuse of retired grants or automatic key rotation. Revocation or
rotation requires disabling this integration and an independently reviewed
migration; do not silently replace the config, move history into another
installation, or delete quarantine rows.

## Signed input protocol

Every `SignedStatement` contains `statement` and `endorsements`. A statement has
version `uptime-ramp-award-attribution/1`, installation/tenant/business/environment/
evidence-mode audience, purpose `kind`, immutable event `id`, `issued_at`,
`expires_at`, and `body`. All times require timezone offsets. The maximum signing
window is 24 hours. Ingestion checks the current clock and current witness grant;
the CLI offers no replay-clock override.

Use `signing_bytes(config, statement, subject)` in an independent offline signer.
It returns canonical JSON bytes of domain, whole-office-config hash, role,
subject, public key, and statement. JSON uses sorted keys, compact separators,
ASCII escaping, and no NaN. The signer supplies the lowercase hex Ed25519
signature. It is not a signature over body alone. This binds purpose, installation,
human role, mode, tenant, business, scope, and all record hashes, preventing
reflection between roles or methods. Only registered public witnesses verify.

The Pydantic models in the module are the executable schemas; extra input fields
are rejected. `Evidence` always has `reference`, `sha256`, and `method`.

1. **`filed_claim` / `register_claim`:** The registrar signs `FiledClaim` with
   `claim_id`, `dispatch_sha256`, `local_contract_id`, `claimant_operator_id`,
   full `scope`, `scope_verification`, and `bills`. Each bill includes native
   `bill_id`, `eligible_minor`, and independently reviewed scope evidence.
   A proven initial filing must already exist in `claim_dispatch_identity_v2`
   or the supported v1 history. `filing_identity(claim_id)` returns a normalized,
   receipt-bound digest for review. The store checks the original stored packet,
   receipt, scope and economic key; it never resolves history from today's
   fixtures or terms. Local simulator and local outbox receipts authorize only
   `MOCK` attribution.

   **`ACTUAL_NATIVE` additionally requires `external_filing` and signatures from
   both `claim_registrar` and `vendor_verifier`.** The preexisting filing must use
   the platform's `historical-receipt` route and contain exactly one original
   external receipt corroborated by its `inbox_delivery` record. A supplement
   alone, bare reservation, simulated dispatch, or local outbox cannot qualify.
   `ExternalFilingWitness` has `evidence_mode="ACTUAL_EXTERNAL"`, `receipt_id`,
   `receipt_sha256` (the digest of the complete persisted original evidence fact),
   `received_at`, `submitted_to`, `channel`, `verification`,
   `authority_verification`, and `independence_verification`. The channel must
   be a vendor portal, signed document, or authenticated correspondence. The
   three verification fields use `Evidence`. Both signatures cover the entire
   statement, including exact account, agreement/version, service, month,
   beneficiary, product, bills and the external custody attestation.

   A platform source grant authenticates intake only. It does not establish
   external delivery or turn `LOCAL_SYNTHETIC` evidence into a real filing. The
   separately enrolled witnesses must independently verify the retained external
   original through the stated channel; they must never attest a simulated
   record as `ACTUAL_EXTERNAL`. `MOCK` witnesses cannot authorize actual native
   attribution. This is an explicit office trust decision, not a boolean the
   applicant or inbound connector can set. The journal binds each vendor/receipt
   to one claim, including across accounts, in the same transaction as registration.
   No real external witness or commercial authority is supplied by this repository.
2. **`vendor_award` / `import_award`:** Both the vendor verifier and independent
   human finance approver sign `VendorAward`: claim ID and immutable registration
   hash, exact scope, unique `vendor_award_ref`, integer `amount_minor`, and
   confirmation evidence. Confirmation requires a vendor portal, signed vendor
   document, or authenticated vendor correspondence, plus documented vendor
   authority and independence verification. A Ramp posting is not an eligible
   confirmation channel. Scope registration must predate the signature. A reused
   award reference or contradictory award amount quarantines attribution.
3. **`native_snapshot` / `observe`:** The capture witness signs `NativeSnapshot`.
   Its sanitized credit/bill fields match credit-sync's `credit_observation()`
   projection, with added `capture` evidence. It includes `observed_at`, source,
   provenance reference, explicit granted scopes, availability and completeness.
   `ACTUAL_NATIVE` accepts `LIVE_RAMP_SANDBOX`; `MOCK` accepts
   `DETERMINISTIC_REPLAY`. A caller's boolean or label cannot promote a mock:
   the pinned office and capture witness must establish the custody class.
4. **`attribution` / `attribute`:** Finance signs `Attribution` for an existing
   award, its claim registration hash, current snapshot hash, exact credit UUID,
   integer `posted_minor`, currency/rate, and explicit cumulative bill shares.
   Each application has `bill_id` and `amount_minor`; zero is explicit. The
   required basis is `EXACT_EXPLICIT_ALLOCATION`, with retained scope verification.
   The award and observation must already have been received before approval.

## Allocation and change semantics

N:M attribution is supported: several awards may share one credit, and an award
may span credits and bills. Every allocation names exact IDs and amounts.
SQLite serializes intake with `BEGIN IMMEDIATE`, and triggers cap total posted
shares per credit and per award, applications per allocation and native pair,
and bill capacity within the same snapshot. Registered claim bill eligibility
also caps cumulative applications. Registered bill ownership and credit ownership
remain bound to the same vendor/account/beneficiary/contract/version/product/currency
across snapshots.

An unallocated remainder is displayed as unattributed. No proportional split,
`min(award, application)`, matching by amount or name, entity-equals-beneficiary
comparison, reference-bill-equals-contract comparison, inferred FX, or inferred
application amount is allowed. Missing split basis returns
`SPLIT_BASIS_REQUIRED`; partial coverage requires explicit source-backed shares.
Sparse money and scope remain unknown. Unknown money is not zero.

Both the exact credit and scoped bill must be accessible and internally
consistent. Reciprocal native relations are checked for consistency; two Ramp
views are not two independent sources. Draft applications are reported separately
and cannot substantiate posted-bill attribution. Unknown archival state or bill
status cannot qualify; supported payable statuses are `OPEN`, `PAID`,
`PARTIALLY_PAID`, `SCHEDULED`, `APPROVED`, and `PAYMENT_PENDING`.

Exact retries within the signing window return the original receipt. Repeated
cumulative reads are never added as deltas. A new snapshot requires a new human
signature, including when an application legitimately increases. A normal
decrease in remaining balance does not cause quarantine; an increase in remaining,
unapplication, changed credit total/scope, conflicting reciprocal relation,
disappearing credit in a complete list, or voided/archived record does. Late
conflicting snapshots also quarantine. Archival may be normal cleanup, so its
reason says review required rather than asserting financial reversal.

Quarantine is durable and invalidates current attribution, including prior
accepted bindings; a subsequent clean-looking poll does not clear it. Native
observed values remain visible. No automated reversal or conflict-resolution
workflow is included. An independently authorized finance owner must investigate
outside this API and commission a reviewed resolution/migration. This conservative
policy can delay attribution, but does not mutate any provider balance.

## Root workspace integration and operator entrypoint

Root owns `RampWorkspace`; this change does not edit that shared file. Instantiate
the companion only after existing workspace authority and native business
initialization. Load its office config once through the reviewed operator path:

```python
from uptime.ramp_award_attribution import AwardAttributionStore, load_office_config

office = load_office_config(operator_selected_public_config)
awards = AwardAttributionStore(workspace.path, office)
# Add a separate field alongside the existing simulated credit journal.
verified_observations = awards.summary(workspace.tenant, installed_business_id)
```

`summary` is a local read transaction and performs no provider calls. It returns
snapshot identity/time/freshness, completeness, captured credit count, historical
accepted award/binding counts, current verified binding count, quarantine reasons,
and each credit's observed/attributed/unattributed amounts. Historical counts are
marked `awards_are_historical`; a suspended or stale attribution is not current.
Missing awards or bills retain `OBSERVED_UNATTRIBUTED`, `POSTED_UNATTRIBUTED`, or
`APPLIED_UNATTRIBUTED`. Do not add these values to simulated reconciliation,
revenue, ROI, or recovered-cash cards. `MOCK_APPLIED_ATTRIBUTED` must remain labeled
as mock. A complete, authentic empty capture shows zero captured credits; absent
or unavailable observations retain a null count.

The root capture adapter can feed the existing sanitized `credit_observation()`
body plus retained capture evidence to the offline capture witness. It must not
self-issue a signature, use source labels as authentication, or route unsigned
fixtures directly into `observe`. If no reviewed office/capture witness exists,
keep the existing unattributed journal; do not fabricate an attestation.

```sh
uv run --locked python scripts/ramp_match_award.py \
  --db /operator/workspace.sqlite --office-config /operator/private/award-office.json summary
```

Other commands are `filing-identity CLAIM_ID`, `register-claim SIGNED_FILE`,
`import-award SIGNED_FILE`, `observe SIGNED_FILE`, and `attribute SIGNED_FILE`.
They write only this local observation journal. The CLI never reads Ramp
credentials, submits a claim, signs an award, or makes an external request.

Run `uv run --locked pytest tests/test_ramp_award_attribution.py` for deterministic
tests. Full integration still requires the root's post-merge `uv run --locked
pytest` gate. No test or included example supplies real commercial authority.

## Canonical registry compatibility and validation

The v2 economic key excludes agreement version, normalizes vendor/service labels
with NFC and case folding, and preserves opaque account IDs. Agreement version
still binds the approved historical packet; a later version cannot mint another
monthly claim or silently replace the original packet's terms. The historical
receipt route does not retain a terms version; the independent signed filing
attestation must establish it. Current contract state cannot fill that gap.

The reader uses the shared `claim_identity` normalization and legacy receipt
validators. Supported v1 correspondence and legacy records are resolved from
their saved packets/approvals and their versioned v1 hashes are checked before
mapping to the v2 key. Identical v1/v2 copies coalesce; conflicting owners of a
canonical obligation fail closed. Unindexed receipts from an older writer,
orphan reservations, unknown historical remedies and inconsistent metadata need
reconciliation through the existing claim migration workflow. Award attribution
never creates a replacement registry table, releases a reservation, or runs a
migration during review or summary.

Normalized registration digests survive additive v1-to-v2 migration. Earlier
`MOCK` registrations that signed a physical v1 row remain usable only while the
exact original row and corroborating receipt still exist. Unsupported old
`ACTUAL_NATIVE` registrations without the new independent external witness do
not become current verified attribution. No stored approval is rewritten.

Receipt identity, packet/scope, source fact and current witness validity are
rechecked before award import, allocation and each current summary. Changes
suspend attribution while preserving observed provider amounts and historical
rows. Receipt uniqueness and allocation caps remain transactional. Filesystem
owners can bypass SQLite triggers; tests simulate that explicitly rather than
weakening ordinary write protection.

The corrective work started on `b3a5edadb979ca819cff159c960faf2e2db74b40` with
**57 failures and 20 passes** in the original attribution test file. The old
positive ACTUAL test used only an opaque fixture reservation; it was replaced
by coverage of the platform receipt and independently signed custody protocol.
Tests use generated identities, keys, packets and captures and establish no
real claim, award, Ramp write, or recovered cash.

The remediation also read packet/review 42 from the integration worktree:
`42-release-authority-and-independent-critique.md` SHA-256
`086d2d29d76122e94cf6b5e17ec808b886addb9d429eb8d86a3fe997b54991c5`, and its JSON
review SHA-256
`5a4bd4e285f7a5ac009b619b284214bd652cf8ac20a6c5ac226c12838f837ba4`.
That saved review requires out-of-band vendor-key enrollment and rejects inferred
external authority. The office's separately enrolled vendor verifier and exact
custody signatures enforce this boundary; ordinary source keys are excluded.
These are existing reviews of the design, not an independent review of this
patch. **OPUS_BLOCKED for a new consult:** this task explicitly prohibits network
and credential access. The changes are local and reversible; no actual office
has been enrolled, real filing certified, or external action authorized here.

Validation commands (offline dependency resolution):

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_ramp_award_attribution.py tests/test_ramp_award_claim_integration.py
UV_OFFLINE=1 uv run --locked pytest
```

The integration tests exercise original legacy/correspondence receipts, both
physical registry versions, additive migration and old signatures, canonical
version/label duplicates, external original versus supplement, missing/mock or
mismatched witnesses, receipt reuse across accounts, later evidence changes,
read-only summaries, and the operator CLI. Root wiring remains a separate
`.summary(tenant, business)` read; no shared workspace or claim-intake code changed.

Final focused validation: **111 passed** across the attribution and claim-join
files. The broader claim/correspondence/allocation/reconciliation/native-credit
selection: **370 passed**, with one dependency deprecation warning. Compilation,
CLI help, the CLI persistence smoke test and `git diff --check` passed.

The final full locked suite reports **1,821 passed, one skipped, two failed**
(one dependency deprecation warning; 213.31 seconds). The two failures require a
loopback socket that this task's sandbox rejects:
`test_source_config_v4.py::test_delivery_cli_posts_original_file_to_real_loopback_and_prints_only_receipt`
and
`test_v4_authority_browser.py::test_real_browser_sibling_cannot_exfiltrate_or_replay_authority`.
Both independently reproduce on a pristine archive of the base commit at
`listener.bind(("127.0.0.1", 0))` with `PermissionError: Operation not permitted`.
No permission escalation, credential access or external network call was used.
