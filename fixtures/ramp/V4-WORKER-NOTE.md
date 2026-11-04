# Ramp V4 worker handoff / consequential decisions

Owner D, branch `v4/ramp`, base `18afaa6`. No credential inspection or live
provider operations were performed by this worker. The central lead owns the
mandatory Claude Opus 5.5 review and any authorized Mac-side capture.

Review packet: routine capture must never request write scopes. A dedicated
token-only diagnostic can explicitly request write scopes without reading
records or mutating bills. Draft execution requires an explicit vendor UUID,
an explicit authorization argument, an environment feature gate, exact returned
scopes, and the local operation journal. The broader OAuth write permission is
not itself authorization to create a bill. Ambiguous creations are not retried.

Capture checksums detect edits/corruption, not malicious recomputation or provider
authenticity. Saved results carry observation time and freshness separately from
their historical source. The original V3 file is pinned by its archive digest;
it is historical, lacks V4 canonical fields, and cannot be used as a current V4
financial input. A fresh capture does not establish a contract or allocation.

Provider `vendor.id` and `entity_id` are preserved. An entity is not a vendor's
customer-account identifier; the Bill schema does not supply the latter. No
account ID is inferred from a bill, ledger category, or demo fixture. GL-account
selection IDs are retained separately from customer identity.

Official sources inspected: https://docs.ramp.com/openapi/developer-api.json
(archived public schema at `/private/tmp/uptime-v3-audit.NkRatL/ramp-official.json`,
SHA-256 `742ef47d2af8734d49b4913e254bf28a6e287d72491591781f0238c696070091`),
and https://support.ramp.com/accessing-the-developer-api/ (retrieved 2026-11-04).
Direct refresh of the OpenAPI failed because this worker's shell cannot resolve
the host; the web tool also could not retrieve that JSON. The archived schema is
used with that limitation, not represented as a newly fetched schema.

The token API establishes the returned grant, missing scopes and unexpected
scopes. It does not expose the app's allowed-scope configuration or diagnose why
a scope was omitted. No app-scope administration endpoint was identified in the
reviewed schema. A sandbox administrator must inspect Developer apps → matching
app → Grant types / Client credentials and Scopes / Configure allowed scopes.
An employee's Bill Pay role and web sign-in state do not establish an OAuth grant.
If a needed scope is unavailable, the admin may contact Developer API support
with sanitized grant metadata. This worker makes no scope configuration change.

Implementation results and lead entrypoints will be appended before delivery.

## Delivered behavior and integration contract

- `capture(provider)` requests `vendors:read` and `bills:read` only. It performs
  genuine list + same-ID detail requests through the fixed sandbox transport.
  List limits: page size 2–100, pages 1–10, default 20 × 3. Detail reads are
  separately capped at 1–100 per resource, default 20. `list_complete`,
  `detail_complete`, counts, and `has_next` expose truncation. Unsafe next URLs,
  changed filters, duplicate IDs and repeated cursors fail closed.
- `scope_probe(provider, include_write=True)` requests read/write together and
  write alone after read grants. No resource request or mutation occurs. Output
  distinguishes exact, missing, unexpected, and absent-scope-field grants;
  authentication/access HTTP failures remain distinct from scope omission.
- V4 canonical bills retain `vendor_id`, `entity_id`, separate
  `accounting_field_selections`, quantity, unit price, and an arithmetic check
  (`MATCH`, `MISMATCH`, `UNAVAILABLE`). Names, memos, contact data, URLs, secrets,
  and raw replies are omitted. `account_id` is explicitly unavailable, not
  synthesized. Null or malformed ordinary bill status/identity fails closed.
- `ramp_snapshot()` remains offline. New captures contain `capture_version=2`
  and a SHA-256 checksum. Snapshot output adds `capture_status`: freshness,
  integrity, age, legacy flag, and `usable_for_evaluation`. Default freshness
  policy is 24 hours, configurable through the loader; future timestamps and
  invalid captures are unavailable. Old pinned captures remain viewable as
  historical replay. No historical timestamp or captured record was changed.
- Billing/ledger owner B should consume the canonical fields without remapping
  `entity_id` to `account_id`. Require `capture_status.usable_for_evaluation` and
  independently trusted local custody before using current saved observations.
  This flag also requires complete list/detail coverage and no quantity/rate
  mismatch. It establishes no contract binding, award, tenant allocation, or
  permission. Missing quantity/rate stays unknown. A provider total alone does
  not establish tax-exclusive spend. The existing `ProviderLine` has no unit-rate
  field, so do not discard the canonical `unit_price` when extending its mapper.
- UI owner should expose `capture_status.freshness` and `.integrity` alongside
  historical source labels. `LIVE_RAMP_SANDBOX` describes where a saved record
  originated; `DETERMINISTIC_REPLAY` indicates the display is from disk.
- Draft writes remain disabled unless `RAMP_ENABLE_DRAFT_WRITE=1`, explicit
  authorization is passed, and the designated vendor occurs in the bounded
  vendor read. No automatic first-vendor selection. The fixed payload is exactly
  1,000 demo units × USD 37.50 = USD 37,500, accounting sync disabled. The approved
  scope must cover that exact sandbox scenario before the lead runs it. Only a
  private local journal's tagged draft can be read back and receive the fixed
  memo update. Readback requires the same ID/vendor/tag, DRAFT, NOT_SYNCED, exactly
  one inventory line, exact quantity/rate/amount, and memo. Lost creation replies
  require manual reconciliation; they never trigger another create. The journal
  and a token are not provider-side idempotency guarantees.

## Lead entrypoints (not run live by worker)

Run from the merged repository on the authorized Mac. These commands use only
nonsecret environment flags; the provider reads the already configured private
credential file locally. Do not pass credentials in CLI arguments.

```sh
# Routine bounded read capture; no bills:write request.
RAMP_ENV=sandbox RAMP_BASE_URL=https://demo-api.ramp.com \
  /private/tmp/uptime-v4.WTuRU4/venv/bin/python scripts/ramp_probe.py

# Read-only grant diagnosis including the explicitly requested write-scope probe.
# No bill/resource reads and no bill mutations; output contains token metadata only.
RAMP_ENV=sandbox RAMP_BASE_URL=https://demo-api.ramp.com \
  /private/tmp/uptime-v4.WTuRU4/venv/bin/python scripts/ramp_probe.py \
  --scope-only --include-write-scope --output runtime/ramp-scope-v4.json

# Only after lead confirms exact authorization, scope and designated sandbox vendor.
# Replace the placeholder with the approved canonical UUID; never choose a random vendor.
RAMP_ENV=sandbox RAMP_BASE_URL=https://demo-api.ramp.com RAMP_ENABLE_DRAFT_WRITE=1 \
  /private/tmp/uptime-v4.WTuRU4/venv/bin/python scripts/ramp_probe.py \
  --verify-draft --authorize-draft --designated-vendor-id APPROVED_SANDBOX_VENDOR_UUID \
  --journal runtime/ramp-operations-v4.sqlite
```

The scope CLI exits 1 for missing/unexpected grants while still producing sanitized
proof. Capture exits 1 for failed capabilities. Scope proof cannot overwrite the
standard bill capture. Credential/network exceptions are never printed verbatim.
`--help` does not load credentials.

The V4 request file was not staged in this worktree at implementation time; the
worker followed the explicit D assignment. No nested agents or model reviews were
run by this worker. Lead must perform the required real Opus review for the
security/financial decisions above before enabling draft writes.

## Validation

Credential-free tests cover grants, token-only isolation, HTTP authentication
classification, hostile pagination, truncation, canonical identity and ledger
fields, quantity/rate properties, altered/stale/future captures, CLI defaults and
feature gates, private journals, ambiguous requests, and unchanged-total draft
corruption. Hypothesis is installed in the lead-provided shared venv; the lead
must include Hypothesis in the integrated development dependency lock if not
already staged on its branch. This worker does not own pyproject.toml/uv.lock.

Final worker validation: shared Python `-m pytest tests/test_ramp.py
 tests/test_ramp_v4.py -q`: **71 passed**. Shared Python `-m pytest -q`:
**536 passed**, one pre-existing Starlette/httpx deprecation warning, 14.84 s.
`compileall`, CLI `--help`, and `git diff --check` passed. No merge was performed
in this worker; lead retains the required `uv run --locked pytest` after merge.
