# Let one named browser extension frame the app in a side panel

Status: implemented on `work/sidepanel-server-20261109`; not part of the frozen submission build. Decided November 9, 2026.

## Decision and authority

Ronok chose a real Chrome side panel that shows Uptime beside the Ramp bill open in the browser. He said so in the judge session at about 13:45 PST, which relayed his message to the coordinator: a real side panel is the best idea, because sign-in security is not the priority for the demonstration. At 14:34 PST he confirmed to the coordinator directly that the current build is frozen first and the panel is built as a follow-on.

The app refuses all framing today (`frame-ancestors 'none'`). The panel needs one exception. `create_app` gains `side_panel_origin`, and both commands that serve the app gain `--side-panel-origin`: `scripts/serve.py`, and `scripts/setup_northwind.py`, which serves the walkthrough. When an operator supplies exactly one `chrome-extension://` origin, the response policy names that origin in `frame-ancestors`. Without the option nothing changes. The option belongs to one served process: it is validated before anything is written or bound, and it is never stored in a workspace or database.

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

`tests/test_side_panel_framing.py`, 41 cases:

- the default policy is byte-for-byte what it was;
- with the option, only `frame-ancestors` differs and it names exactly the one origin;
- 24 malformed values are refused, including a wildcard, web origins, Ramp's origins, two origins, a trailing slash, injected directives, other browsers' schemes and non-strings;
- pages, static files, a missing page and an unauthenticated read all carry the policy, with and without the option;
- a POST from the extension's origin is refused, including the sign-in challenge, with and without the option;
- the serve command refuses a bad value before it listens or creates a database, and refuses the option on an enrollment, which serves nothing.

`tests/test_setup_side_panel.py`, 9 cases (role 2): the walkthrough setup passes the option to the served app on create and on resume, refuses a bad value before any workspace exists, never stores it, and produces the same package digest and the same four-decision walkthrough with and without it.

No existing test changed. The new tests fail against the code as it was before each change, so they do exercise it.

## The extension, and what a real browser showed

`extension/` holds the panel: a manifest, a one-line background script, a page with one frame, and about sixty lines of script. It asks Chrome for the side panel and for the addresses of `https://demo.ramp.com/` tabs only; it has no general tab permission, no content script, no storage and makes no request. Its public key pins the ID `kibophanbmnepbmhpampfagpjfhjfcnl`. Five JavaScript checks cover the address parsing, the routes, the ordering of tab lookups, the manifest's permissions and ID, and a source scan for requests, storage, page scripting and injected markup. The repository's check workflow runs them through `node --test`, and a wrapper runs them inside `uv run --locked pytest` as well.

Checked on November 9, 2026 with the unpacked extension loaded into a throwaway Chrome 157 profile, against a test workspace started with the option. Ramp's site was not contacted; the Ramp-shaped address was answered by a local stub.

1. The server sent `frame-ancestors chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl`.
2. The extension loaded under that ID and its panel page framed the app at `#records`.
3. Sign-in worked inside the frame, and the "Verified Ramp record" panel was visible.
4. With a tab on `https://demo.ramp.com/bill-pay/bills/list/<bill id>` in front, the label read "Ramp bill f74ba12c…" and the frame moved to `#ramp-bill/<bill id>`, still signed in.
5. A tab on another site with the same path was not followed: the label read "No Ramp bill open" and the frame returned to `#records`, still signed in.
6. A different page that tried to frame the app was refused by the browser.

Not checked: the side-panel container itself, which a person opens from the toolbar; real Ramp pages; and loading into a person's own Chrome. Not built yet: the `#ramp-bill/<bill id>` page in the interface. Until it exists that address falls back to the workspace's default page, so the panel must not be filmed or shipped before it lands.

## Criticism from Claude Opus 5.5

Asked on November 9, 2026, after the server option, the extension and the setup option were written. The reviewer was a separate read-only session given the diff and the surrounding code, not the conclusions above. It named its model as `claude-opus-5-5`; that is the session's own statement and the harness's model selection, with no separate provider receipt.

**Its conclusion.** A framing page cannot cause a state-changing action and cannot read the framed page, and a server started without the option sends the same policy as before. It found no serious defect. It confirmed the origin check, validation before writing or serving on every path, the absence of cookies, `postMessage` and web-accessible extension pages, and that the bill identifier is a strict identifier that only ever enters the address fragment.

**What it found, and what was done.**

| Finding | Disposition |
|:---|:---|
| The extension's JavaScript checks ran in the check workflow's `node` step but not inside `uv run --locked pytest` | Fixed: a pytest wrapper runs them |
| The rollback below omitted the setup command, its tests and the extension; following it would have broken setup | Fixed below |
| The extension's README said the panel tells the app which bill is open, while the app had no bill page yet | Fixed: the README states the dependency |
| `scripts/serve.py --enroll` returned before the option was checked, so a bad value passed silently | Fixed: the option is checked first, and refused on enrollment |
| Tab lookups could finish out of order and leave the panel on an earlier tab's bill | Fixed: only the most recent lookup moves the panel, with a check |
| The setup command prints the framing line even when it is not serving; the reopen for a public-proposal configuration has no test | Sent to role 2, which owns that command |
| No automated test pins what Chrome itself enforces for an extension origin in `frame-ancestors` | Accepted as a limit. The real-browser check below is run by hand; its script is kept and will be committed with the final check once the bill page exists |

**An existing gap it noticed, not introduced here and not changed here.** Responses that return before the header middleware carry no security headers at all: a request for the wrong host, a cross-origin POST's 403, an oversized body's 413 and an unhandled 500. They are short JSON bodies with nothing to click, so the consequence for framing is negligible, but they were never covered by `frame-ancestors 'none'` either. Closing that gap is a change to the frozen application's request handling and is left to its owners as a follow-up.

**Dissent kept.** Switching to a tab that is not a Ramp bill returns the panel to the workspace's records page, which drops anything half-typed in the panel. The reviewer noted this. It stays: a panel that kept showing one bill while its label said no bill was open would misstate what is open.

## Rollback

Remove `side_panel_origin` and `panel_origin` from `uptime/server.py`, the `--side-panel-origin` option from `scripts/serve.py` and from `scripts/setup_northwind.py` (including the argument it passes to `create_app`), and delete `tests/test_side_panel_framing.py`, `tests/test_setup_side_panel.py`, `tests/helpers/side_panel_extension.test.cjs` and `extension/`. No stored data, signature or approval depends on any of it. A server started without the option already behaves as before.
