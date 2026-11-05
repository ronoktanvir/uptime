# Advanced companion integration

Implemented in worktree `advanced_ui`, branch `remediate/advanced_ui`, from base
`1294bd4a1b739829092ee659c5aa4f45ea3656df`. Scope is `web/app.js`,
`web/v4_ui.js`, `web/v4_style.css`, new tests/helpers and this document. Backend,
main, auth helper, Ramp component and index markup are unchanged. Coordinator
review is supplied by the task; packet42 remains pending. This change does not
claim a new decision review or external authority.

## Routes and backend contracts

| Route | Working projection |
| --- | --- |
| default, `#ramp`, `#ramp/<encoded ID>` | Existing primary Ramp worklist and matched evidence inspector |
| `#advanced` | Accessible workflow catalog, `/api/ramp/workspace` integrity and credit reconciliation observations |
| `#vendors` | Existing `/api/vendors` catalog plus detail expansion, source-grounded candidate intake, independent tests, active evaluation, returned version actions |
| `#disputes` | Existing `/api/correspondence/claims` list and scoped case creation |
| `#disputes/<encoded ID>` | Authenticated claim detail, untrusted inbound evidence, receipts and returned actions |
| `#dashboard` | Preserved V3 evidence ledger; inbox case inspectors link to correspondence context |
| `#lab`, `#onboarding` | Preserved V3 `/api/onboarding` lab |
| `#regression` | Server-declared `/api/dashboard` portfolio/seeded cohorts, without client cohort inference |
| `#policy`, `#integrations`, `#rehearsal` | Existing routes; rehearsal remains an alias for dashboard |

The existing static mount serves the lazily loaded V4 assets. Companion links
are installed by app.js, preserving the primary Ramp entry. Expanded navigation
scrolls in short desktop windows. V4 forms and records use single-column compact
layouts and wrap long evidence identifiers.

## Review and authority

Portal forms have input → exact request review → confirm stages. Edits invalidate
the reviewed payload. Confirm uses the existing `uptimeAPI` challenge/signing
client and real backend routes. Public contract text and private customer overlay
remain distinct, with no sample values or inferred entitlements. The source text
is displayed as text, never executable markup. Existing server-returned lifecycle
and dispute actions remain available through their original routes.

Writes are disabled unless a reviewer signs in during this page lifetime, the
session reports deployment approvals enabled, and a fresh `/api/policy` read
reports reviewer access. Reloading loses the auth helper's in-memory signing key;
forms remain read-only until sign-out/sign-in restores it. This browser gate is
only a presentation guard: the backend still verifies fresh proof, role,
mandates, current source/version state and exact operation permission.

Successful writes reload current server state; correspondence actions reload the
same claim. Generated cases open their inspector after refresh. Lost responses
retain an explicit unknown-outcome state and disable retries until refresh.

The legacy Ramp plan advertises provider paths for entities not supported by the
installed native binding. The app now displays unsupported entities as
`UNSUPPORTED_ENTITY`, bill plans as `READ_ONLY_PROPOSAL`, retains original status
as `server_status`, and removes executable method/path/scope presentation. It
preserves returned sources and delivery state. No browser control publishes a
native comment, executes approval, ingests service events or communicates with a
vendor. No credentials or authority shortcuts were introduced.

## Verification and limits

Commands:

```
node --test web/browser-contract.test.cjs web/v4_ui.test.cjs tests/helpers/advanced_companion.test.cjs
UV_CACHE_DIR=/private/tmp/uptime-uv-cache uv run --locked pytest -q tests/test_advanced_companion.py tests/test_vendor_catalog.py tests/test_correspondence_api.py tests/test_v4_routes_integration.py
```

Node: 29 passed, including all 17 pre-existing V4 tests. Scoped pytest: 70 passed,
2 browser tests skipped because this sandbox denies loopback socket binding.
The new browser tests use generated temporary QA identities, a real local server,
real signing, source intake readback, viewer/deployment gates, route navigation,
and a 390px viewport. They remain runnable outside that restriction; this session
does not claim browser or mobile rendering verification. Static source audit,
JavaScript syntax checks and `git diff --check` also pass.

Credit reconciliation/quarantine fields are rendered exactly from overview.
This backend does not expose signed terms verification aggregate metrics; their
absence is explicitly unknown. No projected money, fabricated passing grades,
external delivery or cash recovery is inferred. The catalog does not add a new
matching engine: Ramp matching and evaluation evidence remain server-owned.
No merge was performed; the full post-merge `uv run --locked pytest` gate belongs
to integration.
