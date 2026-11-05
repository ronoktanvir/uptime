# ADR 0057 — Bind the visible Ramp demo to its own installation

Status: implemented; user-created registration, protected setup, exact browser/API association and write-scope grant verified. Native write proof remains pending.

## Decision and alternatives

Preserve the original credentials, database and observations. Support a separate, explicitly selected protected credential profile for the demo the user has opened. Require exact sandbox business and bill identities; similar vendor names or amounts never establish association. The original account remains a rollback option, not a source of interchangeable identifiers. The [packet](packets/57-native-demo-installation-identity.md) records the alternatives and costs.

Use one credential loader for the read adapter and guarded native writer. A process configuration selects a physical, owner-controlled file outside the repository. File descriptors pin every directory component without following symlinks; the opened file must be a bounded, singly linked regular file. Strict JSON, exact sandbox origin and header-safe strings are mandatory. No HTTP field selects credentials. The origin value is checked but never used for routing.

A read-only connection check uses `GET /developer/v1/business` under `business:read` and `GET /developer/v1/bills/{id}` under `bills:read`. Its bill UUID must equal the UUID in an actually observed `https://demo.ramp.com/bill-pay/bills/list/{id}` URL. This is a one-bill association, not an inventory or provider-signed attestation. A new workspace retains the existing immutable tenant/business guard. Native preflight and dispatch continue to recheck the current provider business, current record, reviewed text and independent authority.

## Independent review and disagreement

Actual Claude Opus 5.5 session: `87c185bb-9d73-443b-8341-e92afa42086f`; packet SHA-256: `766b723526dbf1ed4251e2334d002a80985e4ef090b30564182f64c3774d3d03`. The complete [response](reviews/57-native-demo-installation-identity.json) is preserved.

Accept descriptor-based reads, ancestor protection, negative identity controls, exact native readback, separate app/human identities, sanitized failures and preserving uncertain outbox outcomes. The empty Developer Apps screen is an observation about this signed-in view, not proof that the old app does not exist. The cause of the mismatch remains unknown.

Root disagrees with requiring a second generic choice of demo: the user's latest steering explicitly selects the demo they opened; the administrator handoff also offers returning to the earlier account. A complete UI/API inventory comparison would be necessary to claim matching inventories, but a scoped exact-object read plus verified business is sufficient for a one-bill association. A separate client-ID pin in the workspace would obstruct lawful credential rotation without improving the existing business and exact-object dispatch checks. Profile selection is not authority; neither old/new combination may import into a workspace bound to a different business.

Opus's claim that registration write scopes necessarily appear on every token is contradicted by the observed singleton-scope exchanges and is not adopted. Exact returned grants remain mandatory. Its idempotency concern is already addressed by the existing durable outbox, unique reviewed finding marker, pre-write discussion lookup and read-only uncertain-outcome reconciliation; these controls remain in place. Neither review nor tests authorize registration, agreement acceptance or a native note.

## Validation and rollback

Required new checks: both adapters use the shared loader; unsafe files, JSON and origins fail without secrets; default and explicit profiles remain distinct; process profile changes cannot switch a running writer; exact observed URL/bill and business checks refuse cross-account joins. Existing native tests cover same-thread delivery, unknown outcomes, revocation and no resend. Source-bound results will be added after execution.

The 42 new custody/association tests pass. The initial combined run also passed 135 existing Ramp/native/workspace tests; four new fixture-construction failures were repaired (missing test authentication and entity fields) before the 42-test rerun. These are local protocol/filesystem checks. The actual read-only negative control returned HTTP 404 for the observed UI bill under the unchanged original profile; its private receipt is `receipts/ramp-connection-57/old-profile-negative-control.json`. The user subsequently completed registration, approved the seven scopes and approved protected local storage. The new app reads the identical browser bill UUID and returns a different business UUID from the original profile. Its exact `bills:write` token grant is verified. Capture `67f0c9b50391d5b5624930e50b70c9e44ffa2ca93cd8609cb99fa11b7d2657d8` is imported into a separate database and tenant; original data is preserved. The 704caa5 integration passed 2,607 Python tests. These observations establish a new connection, not the historical cause of the original registration mismatch. No native write is claimed. See the [sanitized connection evidence](../evidence/native-demo-connection-20261104.json).

Stop the new installation before removing its profile selection. Keep its database and outbox. Restarting with an incompatible business must fail the existing binding. Do not overwrite the old credential file, reclassify its captures, delete remote comments or resend uncertain writes.
