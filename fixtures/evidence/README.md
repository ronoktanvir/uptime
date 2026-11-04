# W5 public incident evidence

Source URI: https://status.twilio.com/api/v2/incidents.json

`twilio.json` minimizes the lead's supplied official public intake collected at
2026-11-04T05:00:26.869102+00:00. The raw SHA-256 is
`df6044581ef0bc0df7ac59f25451e24b7030078ccf135d28a27e65c267706310`.
Raw intake and metadata remain untracked; only typed public incident fields are
retained. Update bodies, links, notification fields and other unused text are
excluded. Collection time is an audit observation, not an incident start time.
Missing incident timestamps remain null. No downtime is computed.

Each observation has a canonical JSON content hash; the snapshot has a separate
integrity hash. The raw hash was verified against the supplied intake during
minimization. Hashes provide integrity and reproducibility, not a signature or
independent proof of source authenticity. The lead's collection metadata is the
provenance trust boundary. Historical verification needs the original raw intake.

Integration: `from uptime.evidence import evidence_summary` returns a JSON-safe
view with source arrays, typed items, hashes, collection and audit timestamps,
freshness state and explicit coverage gaps. Default reads are offline and tagged
`LIVE_VENDOR_PUBLIC` plus `DETERMINISTIC_REPLAY`: origin and execution mode are
separate. Pass `as_of` for reproducible freshness/audit results. The 24-hour default
freshness threshold is operational display policy, not a contractual requirement.
A recent-incidents feed never establishes complete historical coverage. Missing or
corrupt snapshots return `UNAVAILABLE`; future collection times report a gap.

Public names/status strings are untrusted display-only data. UI consumers must
render them as text, never HTML or instructions. These observations cannot prove
account impact, affected fees, vendor-defined SLA measurements or entitlement.
No customer telemetry is asserted by this snapshot. `SyntheticTelemetry` requires
explicit tenant, service, timestamps and integer request counts; access through
`for_principal` checks the server-authenticated principal's tenant and labels output
`SYNTHETIC_CUSTOMER`. Do not accept browser-supplied principals.

Explicit refresh (not executed by this worker):

```sh
python -m uptime.evidence_refresh --live --output fixtures/evidence/twilio.json
```

The CLI permits only the exact official HTTPS endpoint, disables redirects by
rejecting non-200 responses, limits body bytes to 2 MB and total reads to 10 seconds,
and stores only a minimized snapshot after successful validation. Failure leaves
the existing snapshot intact and reports unavailable. Replay never calls the
network. HTTP transport uses system TLS verification without credentials or proxy
environment handling. Tests replace transport entirely.

No new entitlement or shared-interface decision is introduced. This implements
review packets 06 and 08 as typed observations; lead approval remains necessary
before adding financial qualification or interpreting public incidents as claims.

Worker validation: offline stdlib smoke checks passed for loading all 50 typed
observations, verifying their hashes, JSON serialization and stale-state handling.
The requested shared-venv `python -m pytest -q` run stalled during pytest imports
(`importlib._bootstrap_external.get_data`); interrupted without a suite result.
No dependencies were downloaded. Parent must run the included tests when the
shared environment is responsive. Git staging was denied at the shared worktree
index lock outside this worker's writable root; working files are left for parent.
