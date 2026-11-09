# Item 9 audit — narrow screens, keyboard, empty and error states, expired sessions (W7)

Audited on the integration head `66be040`, which has the same application code as the round-5 head `6f43a91` (`web/`, `uptime/` and `scripts/` are unchanged between them). Every check used throwaway workspaces on random loopback ports. Ports 8776 and 8777 were never touched.

## What held

| Check | Result |
| --- | --- |
| 390 px width | No sideways scroll on the finance view, Ramp records, vendors or disputes; no page errors |
| Skip link | "Skip to workbench" moves focus to the main region without changing the view |
| After sign-in | The first Tab lands in the workbench content (the first attention item) |
| Error states | The finance view shows "Unable to load this view" with Try again (pinned by `test_finance_browser_90`). Ramp records shows "Ramp state unavailable" with Try again. Vendors and disputes show "State unavailable … refresh". The guide shows "could not answer … Nothing was changed" (pinned). |
| Empty states | The finance view shows "Nothing in this case needs action now." and "No actions available in the current state." (pinned). Disputes shows "No correspondence cases returned." |
| Expired session | On Ramp records, vendors, disputes and the finance view, an expired server session returns to sign-in. Signing in again returns to the same route with current content. Actions and guide questions are covered by `test_finance_browser_90` and `test_vendor_auth83`. |

## Gap found and fixed

After running a recovery step with the keyboard, focus fell to the page body. The next Tab started at the top of the content, so a keyboard user had to tab back through the attention list to reach the next step. Focus now moves to the next offered step after each recorded action, or to the "January recovery" heading when no step remains. A failed action keeps focus where it was. A failed reload, or a later ordinary render, never moves focus.

**No existing test changed.** New tests:

| File | Count | Purpose |
| --- | ---: | --- |
| `web/finance_focus.test.cjs` | 3 | Focus moves to the next step. Focus moves to the recovery heading when nothing remains. No focus move on failure or on an ordinary render. |
| `tests/test_finance_keyboard_95.py` | 1 | Real Chrome, keyboard only, 390 px: skip link, all eleven steps with Enter and focus following each new step, $8,600.00, the guide by keyboard, no sideways scroll and no errors. Without the fix it fails at the first focus check; the run was "Locator expected to be focused". |

Results:

- JavaScript: **104/104**
- New keyboard test plus finance browser, guide suggestions, workspace UI, Ramp UI, finance view, guide and Northwind workflow suites: **109 passed, 1 warning in 92.62s**

Full suite: integration round 6 on a fresh clone of `3f60647`, which contains `f0cfa05` and `2cc59ca`: **4664 passed, 1 warning in 322.63s (0:05:22)**, JS 104/104. Receipt: `docs/v4/evidence/integration-90/verification-3f60647.json`.

