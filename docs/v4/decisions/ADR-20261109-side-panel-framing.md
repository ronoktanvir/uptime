# Let one named browser extension frame the app in a side panel

Status: implemented on `work/sidepanel-server-20261109`; not part of the frozen submission build. Decided November 9, 2026.

## Decision and authority

Ronok chose a real Chrome side panel that shows Uptime beside the Ramp bill open in the browser. He said it first in the judge session at about 13:45 PST ("having a real side panel is the best idea because sign in security isn't the priority here; it's the demo and main engineering promise") and confirmed to the coordinator at 14:34 PST that the current build is frozen first and the panel is built as a follow-on.

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

`tests/test_side_panel_framing.py`, 28 cases:

- the default policy is byte-for-byte what it was;
- with the option, only `frame-ancestors` differs and it names exactly the one origin;
- 24 malformed values are refused, including a wildcard, web origins, Ramp's origins, two origins, a trailing slash, injected directives, other browsers' schemes and non-strings;
- with the option on, a POST from the extension's origin is still refused, including the sign-in challenge;
- the serve command refuses a bad value before it listens or creates a database.

With `tests/test_ramp_ui_v4.py`, `tests/test_v4_authority.py` and `tests/test_opus46_security.py`: 62 passed. No existing test changed. The new tests fail to import against the unchanged server, so they do exercise the change.

## Rollback

Remove the option from `uptime/server.py` and `scripts/serve.py` and delete the test file. No stored data, signature or approval depends on it. A server started without the option already behaves as before.
