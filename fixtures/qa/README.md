# W8 integration and browser handoff

These checks implement the CP1 browser contract in `docs/orchestration/INTERFACES.md`
and the worker's explicit `create_app(db_path, session_secret=..., mode="replay")`
and session-cookie requirements. They do not define a new server API or financial
policy. Source labels are independently enumerated from the V3 spec, rather than
copied from the implementation under test.

## Run the tests

From this worktree, using the existing environment (no synchronization/download):

```sh
../../../outputs/uptime/.venv/bin/python -m pytest -q -ra
```

Before the server is merged, API checks explicitly skip. Missing dependencies,
broken server imports and contract failures do **not** skip. The integration gate
must forbid the missing-server exception:

```sh
UPTIME_QA_REQUIRE_SERVER=1 ../../../outputs/uptime/.venv/bin/python -m pytest tests/test_journey_api.py -q -ra
```

Every test creates its own temporary database and ephemeral session secret.
Python socket connections are blocked during API tests. The test suite never
loads a user database or supplies provider credentials. Do not use `--showlocals`
or HTTP debug logging when running authentication tests.

Coverage includes anonymous reads/writes, invalid bootstrap and cookie tampering,
spoofed role/tenant headers and JSON, forged monetary fields, missing/foreign/null
origins, spoofed host prefixes/ports, cross-site fetch metadata, missing AJAX
markers, legitimate native/same-origin clients, missing cases, unknown actions,
GET mutation refusal, guide injection, separate human actions, exact provenance,
decimal amounts, misleading recovered totals, evidence/clauses/traces, onboarding
views, and persistence after recreating the app. An accepted action with forged
fields is compared against an independent clean replay: safely ignoring extra
fields and rejecting them are both allowed.

Tests discover actual case/action identifiers from the authenticated API. They
do not invent an approve/submit route, require a caller-supplied tenant, or assume
the guide can execute human actions. Authorization and CSRF failures must happen
before business state changes. Rejected attempts may create security audit events;
the global audit log is excluded from business-state equality checks.

## Browser backup

After the actual server and web UI are merged:

```sh
../../../outputs/uptime/.venv/bin/python scripts/browser_replay.py --chrome --output fixtures/qa/artifacts/rehearsal-01
```

Omit `--chrome` to use an already-installed Playwright Chromium. The script does
not install a browser. Playwright recording also needs its installed video encoder.
Use a **new** output directory for each run; existing evidence is never overwritten.

The harness binds its own ephemeral loopback server, constructs a fresh replay
database in a temporary directory, and logs in through the real session bootstrap
endpoint before creating the recorded page. Cookies stay in memory. It blocks
external browser requests and Python network connections, disables service
workers and WebSockets, and retains no HAR, trace, console messages, database,
cookie file, login URL or exception traceback. Rendered URLs and email addresses
are replaced before visual capture. Synthetic replay seed data is a prerequisite;
the harness is not a general-purpose PII scrubber for real customer data.

The recording holds at least 120 seconds of actual UI: dashboard (0–24s), case
evidence (24–54s), Atlassian onboarding (54–78s), policy (78–96s), and mobile
dashboard (96–120s). It uses real visible links/buttons/tabs. No replacement HTML,
API mock or static screenshot is substituted if navigation is unavailable.
Navigation names must be reconciled with W7 after merge. The run checks replay
labels, API errors, JavaScript errors, the main landmark, named buttons and
horizontal overflow at desktop/mobile widths. These are basic accessibility
checks, not a full accessibility audit.

Successful output: `desktop.png`, `case.png`, `onboarding.png`, `policy.png`,
`mobile.png`, `backup.webm`, and a metadata-only `manifest.json`. The manifest has
no URLs, cookie values, case IDs or customer fields. A failed capture removes
partial artifacts rather than presenting them as completed evidence. Generated
artifacts and bytecode are ignored by Git.

## Integration limits and lead-owned decisions

- The current worktree has no `uptime.server` or `web/`. No API behavior, real UI
  navigation, screenshot or two-minute video can be verified here yet.
- This contract does not expose a second tenant/role bootstrap configuration.
  Spoof rejection is covered; authenticated cross-tenant isolation and lower-role
  denial still need a W0-approved fixture/configuration interface. No new auth
  mechanism is introduced by QA.
- No webhook route or idempotency header is specified. Duplicate webhook and
  duplicate submission behavior need W0/W4's actual interface before independent
  endpoint tests can be added.
- Exact financial gold amounts and full award/application journeys need the
  merged replay seeds. Current tests verify representations, evidence and stage
  boundaries; they do not establish correct contract arithmetic or reconciliation.
- Browser capture visits real screens but does not submit human case/onboarding
  actions; those mutations and restart persistence are exercised through the API.
  CP6's full interactive dispute/approval choreography remains unverified.
- HTTP expectations: anonymous requests 401/403; invalid login 401/403/404;
  bootstrap 303; authenticated missing case 404; CSRF 403; malformed/unknown action
  400/404/422. If the server uses other error semantics, coordinate with W0 rather
  than hiding a security failure with broad status acceptance.
- Consequential auth, financial or onboarding decisions remain with the central
  lead and its Opus review. These tests propose no change to those decisions.

## Validation in this worktree

- All three added Python files passed AST syntax parsing.
- Fourteen dependency-free harness safety checks passed using system Python:
  remote/provider connection refusal, browser-origin restriction, output ownership,
  preservation of existing evidence, sanitized failure output, and minimum duration.
  These were direct checks of the harness, **not a successful pytest run**.
- The required existing-environment `python -m pytest -q -ra` was attempted.
  It stalled before collection while reading shared environment files in Python's
  import loader (`_pytest` modules). A diagnostic confirmed the import stack;
  a bounded final retry with plugin autoload disabled and a local bytecode cache
  timed out after 45 seconds. Stalled diagnostics were interrupted. No dependency
  downloads, lockfile changes or environment installation were attempted.
- Running the browser harness returned `CAPTURE_BLOCKED` because the server is
  absent. No screenshots, video or successful capture manifest were produced.
- The API tests remain prospective and must run in strict mode after integration.
