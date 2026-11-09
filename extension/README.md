# Uptime side panel for Chrome

A small Chrome extension that shows your local Uptime workspace in the browser's side panel, beside the Ramp bill you have open. It is a browser side panel, not a Ramp integration: nothing runs inside Ramp, and nothing is written to Ramp.

## What it does and does not do

- **Does:** frames the real Uptime page and tells it which Ramp bill is open, using Ramp's own bill ID from the tab's address.
- **Reads:** only the address of the active tab, and Chrome shows it that address only for `https://demo.ramp.com/`. Tabs on any other site read as "No Ramp bill open".
- **Does not:** read or change Ramp's page, hold a credential, store anything, or make a request of its own. Sign-in happens inside the framed Uptime page with the same account and credential file as in an ordinary tab.

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

## The ID is pinned on purpose

`manifest.json` carries a public key, so the extension has the same ID, and therefore the same origin, on every machine. The server allows exactly that one origin to frame it. Only the public key exists; no private key was kept.

Anyone who can load an unpacked extension into your own browser could reuse that public key and obtain the same origin. That person already controls the browser. Keep the framing option off outside a demonstration on your own machine; see [the decision record](../docs/v4/decisions/ADR-20261109-side-panel-framing.md).
