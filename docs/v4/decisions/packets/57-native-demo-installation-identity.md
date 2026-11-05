# Bind the visible Ramp demo to its own installation

This packet contains synthetic/public integration facts only. It excludes credentials, customer data, browser secrets, native object identifiers and private evaluator cases.

## Observed problem

The signed-in sandbox UI and the existing server app credentials expose similarly seeded bill lists but different bill UUIDs. A read-only API refresh confirms that the UI-observed bill UUID is absent from the existing app's complete six-bill list. The UI's Developer Apps screen shows no apps. These observations establish an object-identity mismatch; they do not prove why the credentials or accounts differ. No provider write was attempted. The existing credentials continue to omit write grants.

The user explicitly wants Uptime integrated with this Ramp demo. A native app registration form named Uptime is prepared, but the human must accept the Developer Terms and create persistent access. The original credentials, captures and database must be preserved. Developer documentation supports scoped internal apps and comments on Bill Pay objects. Native comments inform reviewers; they do not block payment. Blank Canvas requires its own configured procurement trigger and cannot be substituted for a bill approval. Browser WebMCP tools expose page context and unsaved form/editor changes; this does not establish a backend integration or arbitrary embedded-page interface.

## Alternatives and preferred implementation

1. Replace the old credential file and reuse its workspace. Lowest initial effort but risks cross-business contamination and loses an operational rollback. Reject.
2. Ask the human to sign into the original account. Could remove the mismatch if available; preserves the old installation but may be the wrong demo. Keep as an explicit human option.
3. Prefer a separately named, protected sandbox credential profile and a new workspace. Add a process-startup-only `UPTIME_RAMP_CREDENTIAL_FILE` selector; HTTP callers and native action payloads cannot set it. Omission retains the existing default. Both read adapter and guarded native writer resolve the same implementation. Credentials require an absolute physical path outside the repository, owner-only parent and regular file, no symlinks, single hard link, current owner, bounded strict JSON, exact sandbox origin and nonempty header-safe client credentials. Never log path contents, tokens, Basic authorization or raw provider error bodies. No arbitrary API origin or production fallback.

After the human installs credentials, exchange the least read grant and read the exact UI-observed bill ID. Record a sanitized association receipt. A mismatch refuses installation; matching amounts or vendor names never substitute. Bind the fresh workspace to the provider-verified business UUID through existing immutable tenant/business guard. Preserve the old database and all original evidence. Writeback remains disabled until explicit scope configuration, object-specific review and exact existing local/native mandates pass. Use the existing reviewed fixed evidence-required message when actual agreement/usage is missing; never publish the constructed price-cap difference as real. Read the created comment back in the identical bill thread, then verify the same text in Ramp UI. Record app identity versus browser-human identity explicitly.

Optional native URL association must use an actually observed sandbox URL and exact matching API UUID. The observed Bill Pay UI route contains `/bill-pay/bills/list/UUID`, unlike the old conservative retention patterns. Do not invent an ERP deep link or broadly relax URL validation. Native link custody and any API comment receipt remain separate.

## Costs, tests and failure risks

Small shared credential loader plus scoped tests; no schema migration or customer OAuth distribution claim. Tests must exercise both read and native adapters, wrong origin, symlink/hardlink/insecure directory, duplicate/unknown JSON fields, malformed credential types, newline injection, missing file, wrong bill/business and preserving the old default. Importing modules or starting the disabled companion must make no provider calls. Model review cannot authorize new credentials, a legal agreement, approval policy changes, payment, vendor communication or an award.

Root's current integrated code passed 2266 tests, but that run predates this proposal and establishes neither a native write nor a matching browser installation. Rollback removes the explicit profile selector, stops the new installation and retains uncertain outbox state for read-only reconciliation; it never overwrites the old credentials, deletes remote notes or silently resends.

Critique the identity proof, configuration/credential boundary and smallest useful native demonstration. Identify concrete unsafe assumptions and required falsifiers. We will retain broad onboarding/dispute scope in parallel.
