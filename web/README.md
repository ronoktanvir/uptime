# W7 finance workbench

Dependency-free browser UI. W0 must serve `web/index.html` at `/`, `web/app.js` at `/static/app.js`, and `web/style.css` at `/static/style.css`, on the same origin as the API. Static references are absolute so case navigation cannot break asset paths. The server establishes the authenticated cookie through its launch/login bootstrap; this UI neither reads credentials nor supplies client roles. No service files were changed because W0 owns the service and routing.

The browser uses the exact routes in `docs/orchestration/INTERFACES.md`. Case and onboarding actions send POST `{}`. The read-only guide sends `{case_id, question}` to `/api/guide`. The browser never calculates aggregate savings or invents financial state. Financial values retain server precision; decimal ordering does not use floating-point conversion. All visible source arrays retain their exact tags. Missing provenance is explicit, including onboarding history strings, which cannot carry individual provenance under the current wire shape.

Policy and integration payloads have no detailed frozen schema, so they are rendered recursively as read-only server fields, including nested sources. New financial/authorization/schema decisions remain with the central lead. No such decisions were introduced here.

## Checks

Run `node --test web/*.test.cjs` and `node --check web/app.js` without installing dependencies. Seven tests cover exact decimal ordering/display, unsafe link schemes, API-driven ledger rendering, inert untrusted markup, encoded case IDs and empty action POSTs, provenance gaps, onboarding validation and unauthorized-link guidance. Test data exists only in test files; the runtime has no financial fixtures.

The DOM contract harness is not a real browser. W8 should verify the integrated service in a browser at desktop and mobile sizes, including dialog focus trapping/Escape, keyboard filter controls, source wrapping and server role rejection. CSS includes reduced-motion support, visible focus, mobile rail/navigation and a horizontally scrollable ledger.

Attempted the requested shared-venv `python -m pytest` from this worktree. Imports stalled before test collection while reading installed pytest files; interrupted rather than waiting or downloading packages. Playwright also stalled while importing installed files. No Python test or browser visual pass is claimed. No merge was performed; the orchestrator must run its required post-merge suite.
