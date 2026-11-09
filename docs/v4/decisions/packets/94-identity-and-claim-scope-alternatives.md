# Decision packet 94: account/agreement identity (D03) and claim scope (D04)

Status: alternatives prepared for a human team decision. The integration owner has a preference but no authority to adopt it. Request: one concise critique.

## Context

A local contract-enforcement application onboards vendor contracts into declarative adapters, then accepts signed claims and evaluates them with deterministic decimal code. Two route families use different identity domains:

- Onboarding accepts free-text account and agreement names, including internal spaces, punctuation and (a defect) trailing spaces.
- Signed claim intake types account and contract as a restricted ID: `^[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}$`, which has no spaces. Vendor and service use a name type that allows internal spaces.
- The economic claim key is SHA-256 over (tenant, case-folded NFC vendor, exact account, exact agreement id, case-folded NFC service, month, remedy). It rejects empty values, leading or trailing whitespace and control characters. Agreement version is required provenance but excluded from the key.
- A ledger helper applies NFC plus strip() to scope fields, the only path that rewrites an identity.
- Claim scope is one strict model with ten required fields (account, vendor, contract, service, component, invoice, incident, currency, month, region). Whole-service monthly obligations have no component, incident or region. Resource obligations may not know the invoice at intake. A filing path selects the obligation-key shape by a vendor-name check.
- Observed effect: two authored public evaluation claims returned HTTP 422 before any model call. In an authored walkthrough, a spaced account turns an ELIGIBLE USD 2,400.00 month into INSUFFICIENT_EVIDENCE because the governing-fee context becomes unreachable. A non-evidence defect is reported as missing evidence.

Constraints: preserve exact source bytes; never slug, trim, case-fold or rewrite historical identities; keep technical route and artifact IDs restricted; keep old signatures, hashes and claim keys valid; distinguish "not applicable" from "missing evidence"; never invent a scope value; manifest byte changes invalidate prior human approvals.

## D03 options

- A. One bounded exact source-identity type for every identity-bearing field: 1–96 characters, printable letters and digits, single ASCII spaces and `. , ' & ( ) + : / _ -`, already-NFC, no leading/trailing/repeated whitespace. Refuse, never rewrite. Existing values are a subset, so no key changes. Add a pre-filing near-duplicate warning.
- B. An explicit immutable mapping table from exact source bytes to an opaque internal ID, created by a reviewed action. Legacy values self-bind.
- C. Tighten onboarding to the restricted ID (operators enter slugs).

## D04 options

- A. Client-chosen discriminated scope variants (service-month, resource-month, incident).
- B. Manifests declare required scope, approved at promotion. Changes manifest digests and invalidates existing approvals.
- C. One scope with typed optional component, incident, region and invoice. The server resolves the governing family from trusted terms and applies a fixed table: required present, not-applicable absent, unknown family refused. Invoice becomes evidence named by INSUFFICIENT_EVIDENCE when the fee basis needs it.

## Preference and strongest counterargument

Preference: D03-A now with D03-B available later for declared aliases; D04-C. Counterarguments: D03-A lets two spellings of one customer create two keys. D04-C needs a code change per new family.

Proposed falsification tests: same key from both intake routes for spaced names, with one filing on retry; different spellings never silently merge; refused-everywhere for trailing, control and non-NFC values; a whole-service claim without component/incident/region evaluates while an invented region is refused; a resource claim without invoice returns INSUFFICIENT_EVIDENCE naming it; all existing keys, receipts and walkthrough amounts byte-identical.

Questions: Which option would you choose, and why? What is missing from the options or the tests? What migration hazard is underestimated? Would you dissent from the preference?
