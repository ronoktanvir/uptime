# Let one named browser extension frame the app in a side panel

Status: implemented on `work/sidepanel-server-20261109`; not part of the frozen submission build. Decided November 9, 2026.

## Decision and authority

Ronok chose a real Chrome side panel that shows Uptime beside the Ramp bill open in the browser. He said so in the judge session at about 13:45 PST, which relayed his message to the coordinator: a real side panel is the best idea, because sign-in security is not the priority for the demonstration. At 14:34 PST he confirmed to the coordinator directly that the current build is frozen first and the panel is built as a follow-on.

The app refuses all framing today (`frame-ancestors 'none'`). The panel needs one exception. `create_app` gains `side_panel_origin`, and `scripts/serve.py` gains `--side-panel-origin`. When an operator supplies exactly one `chrome-extension://` origin, the response policy names that origin in `frame-ancestors`. Without the option nothing changes.

## What it does not change

- **Who may act.** Sign-in and every POST still require this app's own origin. A request carrying the extension's origin is refused with 403, with or without the option. The panel only displays the real page; the reviewer signs in inside that page with the same account and credential file.
- **Everything else in the policy.** Scripts, styles, connections, base URI and form targets stay limited to the app itself.
- **Ramp.** The panel reads only the address of the active tab. It does not read or change Ramp's page, and nothing is written to Ramp.

## Alternatives

- **A docked browser window beside Ramp.** No policy change at all. The judge session recommended it first. Rejected by Ronok for the demonstration: it is not a panel attached to the bill.
- **Remove `frame-ancestors`, or allow any origin.** Rejected. Any page could then draw the app inside itself and trick a signed-in reviewer into clicking.
- **Allow Ramp's own origin to frame the app.** Rejected. Uptime is not embedded in Ramp and must not look as if it were; this would also need Ramp to load it, which Ramp does not do.
- **Read the origin from an environment variable** (the prototype). Rejected for this codebase: an explicit, validated option is visible in the command that starts the server and is testable.

## Residual risk, stated plainly

A Chrome extension's origin comes from the public key in its manifest. Anyone who can load an unpacked extension into the reviewer's own browser can reuse that key and obtain the same origin. That person already controls the browser, so this adds no new reach, but the option should stay off outside a demonstration on the presenter's machine. It is not a control for a hosted product.

## Validation

`tests/test_side_panel_framing.py`, 29 cases:

- the default policy is byte-for-byte what it was;
- with the option, only `frame-ancestors` differs and it names exactly the one origin;
- 24 malformed values are refused, including a wildcard, web origins, Ramp's origins, two origins, a trailing slash, injected directives, other browsers' schemes and non-strings;
- with the option on, a POST from the extension's origin is still refused, including the sign-in challenge;
- the serve command refuses a bad value before it listens or creates a database.

With `tests/test_ramp_ui_v4.py`, `tests/test_v4_authority.py` and `tests/test_opus46_security.py`: 62 passed. No existing test changed. The new tests fail to import against the unchanged server, so they do exercise the change.

## The extension, and what a real browser showed

`extension/` holds the panel: a manifest, a one-line background script, a page with one frame, and about sixty lines of script. It asks Chrome for the side panel and for the addresses of `https://demo.ramp.com/` tabs only; it has no general tab permission, no content script, no storage and makes no request. Its public key pins the ID `kibophanbmnepbmhpampfagpjfhjfcnl`. Four JavaScript checks cover the address parsing, the routes, the manifest's permissions and ID, and a source scan for requests, storage, page scripting and injected markup.

Checked on November 9, 2026 with the unpacked extension loaded into a throwaway Chrome 157 profile, against a test workspace started with the option. Ramp's site was not contacted; the Ramp-shaped address was answered by a local stub.

1. The server sent `frame-ancestors chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl`.
2. The extension loaded under that ID and its panel page framed the app at `#records`.
3. Sign-in worked inside the frame, and the "Verified Ramp record" panel was visible.
4. With a tab on `https://demo.ramp.com/bill-pay/bills/list/<bill id>` in front, the label read "Ramp bill f74ba12c…" and the frame moved to `#ramp-bill/<bill id>`, still signed in.
5. A tab on another site with the same path was not followed: the label read "No Ramp bill open" and the frame returned to `#records`, still signed in.
6. A different page that tried to frame the app was refused by the browser.

Not checked: the side-panel container itself, which a person opens from the toolbar; real Ramp pages; and loading into a person's own Chrome. Not built yet: the `#ramp-bill/<bill id>` page in the interface. Until it exists that address falls back to the workspace's default page, so the panel must not be filmed or shipped before it lands.

## Rollback

Remove the option from `uptime/server.py` and `scripts/serve.py` and delete the test file. No stored data, signature or approval depends on it. A server started without the option already behaves as before.
