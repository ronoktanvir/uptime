# Connect the demo that is actually open in Ramp

The browser session inspected on November 4, 2026 and the original API credentials do not expose the same pending bill UUID. The original app's direct read of the browser bill returned HTTP 404. Its complete bill list also omitted that UUID. This establishes an exact-object access mismatch, not the reason for the different registrations. The signed-in Developer Apps view displayed “Create your first app.” No app was created by the agent, no credentials were replaced and no write was attempted.

The prepared Uptime registration needs the administrator to review and accept [Ramp's Developer Terms](https://ramp.com/legal/developer-terms/developer-terms/api-agreement). The current browser URL is `https://demo.ramp.com/settings/ramp-developer/apps`. Existing captures remain associated with the original API business; they must never be relabelled as the newly opened demo.

## Separate credential profile

Keep `~/.config/uptime/ramp-sandbox.json` intact. Store the new sandbox app credentials separately, for example `~/.config/uptime/ramp-demo-native.json`, with this shape:

```json
{"base_url":"https://demo-api.ramp.com","client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_CLIENT_SECRET"}
```

The physical parent directory must be owned by the current user and mode 0700. The file must be owner-only, regular, singly linked and outside the repository; mode 0600 is suitable. Do not paste credentials into chat, commit them, put them in command-line arguments, or copy them into an evidence receipt. The loader rejects symlinks, including macOS `/tmp` aliases; use a physical path under the user's configuration directory. Group/world-writable ancestors refuse, except root-owned sticky traversal directories; all components are opened without following symlinks.

Set `UPTIME_RAMP_CREDENTIAL_FILE` **before starting** each sandbox process. Omission preserves the old default. Both readers and the guarded native writer use the same loader. An already constructed adapter does not change profiles when the environment changes. The selected file can support credential rotation for the same business; current provider business checks still apply.

Minimum association grants are `business:read` and `bills:read`. The broader read integration also needs `vendors:read`, `transactions:read`, `purchase_orders:read` and `approvals:read`. The administrator must review scope configuration. Native bill comments additionally require `bills:write`, separate exact-action authorization and all existing native guards. An available scope does not prove product entitlement or a successful operation. [Ramp's setup guide](https://support.ramp.com/accessing-the-developer-api) describes allowed-scope configuration and requesting unavailable scopes.

## Verify before importing

Run from the repository, using the exact URL copied from the bill currently open in Ramp. Create the owner-only output directory first. Replace the placeholders; do not synthesize a URL from an old capture.

```sh
UPTIME_RAMP_CREDENTIAL_FILE=/absolute/private/ramp-demo-native.json \
RAMP_ENV=sandbox RAMP_BASE_URL=https://demo-api.ramp.com \
uv run --locked python scripts/ramp_verify_browser.py \
  --bill-url https://demo.ramp.com/bill-pay/bills/list/OBSERVED_UUID \
  --output /absolute/private/association-01.json
```

Success is `ONE_BILL_READ_VERIFIED`. The receipt records separate singleton read grants, the provider business UUID, exact bill UUID, client-ID hash and a sanitized bill hash. It establishes one association, not inventory completeness, browser authentication, provider attestation, write authority or recovered money. A provider refusal exits nonzero and creates no successful association receipt. Outputs are create-only.

Import into a **new database and tenant** after this check, using the same selected profile and `scripts/ramp_refresh_workspace.py`. Never overwrite the original workspace. Its immutable tenant/business binding rejects a different provider business. The original and new installations remain distinct through rollback and replays.

## Native demonstration boundary

Uptime's intended primary review surface is the actual Ramp bill discussion. The advanced companion retains evidence, contract interpretation, onboarding and dispute tools. A truthful first note may report missing governing agreement or usage evidence; the existing constructed USD 40 discrepancy cannot be published as a real exception. An app-created comment needs exact-thread API readback and visible UI confirmation. It does not establish payment prevention or cash recovery.

The inspected UI also exposes page-defined WebMCP tools for page context and selected native editors. Those are browser capabilities, separate from an installed Ramp MCP connector or server-side app integration. No arbitrary embedded-page interface was identified. Blank Canvas, live webhooks and customer OAuth remain separate integration work with their own configuration and proof requirements.
