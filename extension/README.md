# Uptime side panel for Chrome

A small Chrome extension that shows your local Uptime workspace in the browser's side panel, beside the Ramp bill you have open. It is a browser side panel, not a Ramp integration: nothing runs inside Ramp, and nothing is written to Ramp.

## What it does and does not do

- **Does:** frames the real Uptime page and moves it to Uptime's page for the Ramp bill in the active tab (`#ramp-bill/<bill ID>`), using Ramp's own bill ID from the tab's address. That page is part of the interface; on a build without it, the panel shows the workspace's default page whatever bill is open. For a bill the workspace has no saved record of, the page says so.
- **Reads:** only the address of the active tab, and Chrome shows it that address only for `https://demo.ramp.com/`. Tabs on any other site read as "No Ramp bill open".
- **Does not:** read or change Ramp's page, hold a credential, store anything, or make a request of its own. Sign-in happens inside the framed Uptime page with the same account and credential file as in an ordinary tab.
- **When you leave the bill:** switching to a tab that is not a Ramp bill returns the panel to the app's "No Ramp bill open" page (`#ramp-bill`). You stay signed in, but anything half-typed in the panel is lost.

## Panel mode and "Open Uptime"

Framed by this extension, the app shows a compact header (the Uptime brand and the account control) and no navigation rows. Each one-bill page has one primary button, **Open Uptime**, which opens the full app in a browser tab. The app decides it is in the panel only by being framed; the server lets no other page frame it.

The framed page asks the panel to open the tab with one message, and the panel accepts nothing else:

- **Shape:** exactly `{type: 'uptime-open-app', route: '<route>'}`, a plain object with those two keys and no others.
- **Sender:** the message event's origin must equal `origin` in `config.js`, and its source must be the panel's own frame.
- **Route:** one of `overview`, `records`, `cases`, or `cases/<id>` where the id is a letter or digit followed by up to 63 letters, digits, `.`, `_` or `-`. The panel opens `origin + '/#' + route` and no other address.
- **Tab:** the first press opens a new tab. Later presses reuse the tab the panel opened, focusing it and setting the route, while it is still open; a closed tab is replaced by a new one. The panel forgets that tab when the panel is closed. If you navigated that tab elsewhere, a press brings it back to Uptime.
- **The app's side:** it sends the message only to the one extension origin the browser names as its parent (`location.ancestorOrigins`), and it sends a route and nothing else. The new tab has its own sign-in; the panel's signing key is never passed to it.

**Manifest change: none.** Opening a tab, moving a tab the extension opened and focusing its window need no permission. Finding a tab you opened yourself on the app's address would need either the `tabs` permission (every tab's address on every site) or a host permission for the app's address; neither was added, so a tab opened some other way is not looked for and a new one opens instead. The permissions remain `sidePanel` and `https://demo.ramp.com/*`.

## Use it

Loading an extension into your browser is your step; no script does it for you.

1. Start your Uptime workspace with the framing option naming this extension, for example:

   ```sh
   uv run --locked python scripts/serve.py --mode replay --db <your workspace database> --port 8776 \
     --side-panel-origin chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl
   ```

   Without that option the app refuses to be framed by anything, and the panel stays blank.
2. If your workspace is not on `http://127.0.0.1:8776`, change `origin` in `config.js`.
3. In Chrome open `chrome://extensions`, turn on Developer mode, choose **Load unpacked** and select this `extension/` folder. Its ID should read `kibophanbmnepbmhpampfagpjfhjfcnl`.
4. Open a bill in Ramp's demo, click the Uptime toolbar button, and sign in inside the panel.

## Check it in a real browser

`scripts/check_side_panel.py` loads a copy of this folder into a throwaway Chrome profile, signs in inside the panel, moves between tabs and presses **Open Uptime** twice. It never contacts Ramp: a local stub answers the Ramp-shaped addresses. Run it against a workspace started with the framing option:

```sh
uv run --locked python scripts/check_side_panel.py http://127.0.0.1:8776 scripted-test-reviewer <credential file> <folder for screenshots>
```

The last recorded run is in [the evidence folder](../docs/v4/evidence/sidepanel-20261109/real-extension-check.json). It cannot open the browser's own side-panel container; only you can, from the toolbar.

## The ID is pinned on purpose

`manifest.json` carries a public key, so the extension has the same ID, and therefore the same origin, on every machine. The server allows exactly that one origin to frame it. Only the public key exists; no private key was kept.

Anyone who can load an unpacked extension into your own browser could reuse that public key and obtain the same origin. That person already controls the browser. Keep the framing option off outside a demonstration on your own machine; see [the decision record](../docs/v4/decisions/ADR-20261109-side-panel-framing.md).
