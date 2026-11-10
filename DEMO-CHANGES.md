# Demo line changes (demo/film-20261110)

Tests changed on the demo line because the demo deliberately changes a rule. One line of reason each.

## Steps on the Overview, three actors, contract-reading chips, "What was filed" (November 10)

- `web/steps_replay.test.cjs` › "the legend counts equal the recorded steps and agree with the server’s own counts": the legend's labels are now "Uptime agent" and "Received from the vendor and other sources", and the sentence under it changed; the counts it checks are unchanged.
- `web/steps_replay.test.cjs` › "off by default: every step shows at once, nothing is scheduled and no request is added": renamed "on by default on the demo line; turned off, every step shows at once, nothing is scheduled and no request is added", because the replay is on by default on the demo line.
- `web/steps_replay.test.cjs` › "turned on, the next decision’s steps are shown one at a time in recorded order, then all remain": it now starts with the setting off. Its check that the page never says "agent" became a check that no step is attributed to a model, Claude or an AI, because the demo line names the "Uptime agent".
- `web/steps_replay.test.cjs` › "Replay shows the whole list in recorded order; skipping or turning it off shows every step at once": it now starts with the setting off, so the automatic replay on first view does not mix with the replay under test.
- `web/steps_replay.test.cjs` › "browser storage that refuses leaves the setting in memory for this page": it now turns the setting off rather than on, because on is the default.
- `web/filed_view.test.cjs` › "a filed claim prints exactly the packet’s own fields in plain labels": the destination now reads "Vendor claims intake (local)" in place of `isolated-local-simulator`; the exact value stays in the complete server record.
- `web/filed_view.test.cjs` › "the case page shows What was filed before the correspondence, from the record it already loaded": renamed "the case page shows What was filed below the correspondence, closed until opened, from the record it already loaded", because the section moved below the correspondence and is now closed by default.

No assertion about money, authority or what reached Ramp was weakened. No Python test was changed.
