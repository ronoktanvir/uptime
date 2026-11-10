# Template builder: the shared interface (demo line)

Asked for by Ronok on November 10, 2026 (about 04:10 PST), in his words: "for building the templates for contracts it
hasn't seen before could be an orchestrator summoning multiple AI agents reading and then building deterministic
extractors of the contract ... and set up a template for that type of contract which then can be overviewed with human
review", with Jev "for typechecking", built for real, rough and narrow, with no prototype label.

This page is the contract between the three pieces built in parallel. Follow the names and shapes here exactly. If a
shape has to change, change this page in the same commit and say so in your report.

## What a run does

1. **Jev decides which contract type this is** (a `choice` among the templates on file plus `unrecognised`).
2. **Three Claude readers** (claude-opus-5-5 through the local Claude Code CLI, tools off, in parallel) each read the
   contract and return the same fixed set of typed terms, each with the exact sentence it came from.
3. **A Claude template builder** gets the contract and the readers' agreed terms and writes one extraction rule per
   term. A rule is data (a regular expression with one capture group and a type), never code that runs.
4. **Checks**, all real:
   - every quote is in the contract word for word (code);
   - the three readers agree on each term (code);
   - the template, run by Uptime's fixed interpreter on the contract, returns the readers' value for every term (code);
   - the template also reads a second contract of the same form and returns that document's authored terms (code);
   - Jev says each term is supported by its sentence (a yes/no decision with a probability; below 0.90 the term is
     marked for the reviewer). Jev is never used for arithmetic, dates or deadlines.
5. **A reviewer approves that exact template version** (its SHA-256). Nothing is active before that.
6. **The next contract of that type is read by the template alone**: no model call, a few milliseconds.

Nothing here is canned. If Claude or Jev cannot be reached the step says so and no result is shown for it.

## Python: `uptime/jev.py` (Jev agent)

```python
class JevUnavailable(Exception):
    """Carries .sentence, a plain sentence safe to show a reviewer. Never contains the key."""

class JevClient:
    def __init__(self, key_file=None, timeout=20.0):
        """key_file defaults to $UPTIME_JEV_KEY_FILE, then ~/.config/uptime/jev-api-key.
        The key is read from the file at each call, never kept on the object, logged, printed or returned."""
    def choice(self, question: str, options: list[str], context: str) -> dict:
        """-> {"choice": <one of options>, "probability": Decimal, "model": str, "milliseconds": int}"""
    def yes_no(self, question: str, context: str) -> dict:
        """-> {"yes": bool, "probability": Decimal (of yes), "model": str, "milliseconds": int}"""
```

`uptime/jev.py` also provides `FakeJev(choice=..., yes=...)` with the same two methods for tests.

## Python: engine (`uptime/template_builder.py`, `uptime/template_rules.py`) (engine agent)

`TemplateBuilds(directory, claude, jev, samples)` where `claude(system, prompt) -> str` is injected (the real one wraps
the pinned Claude Code CLI; tests pass a fake) and `jev` is a `JevClient` or `FakeJev`.

Start-up: `scripts/setup_northwind.py --serve --template-builder` turns the feature on (needs the Claude Code CLI, as
`--model-jobs` does). Without the flag `GET /api/template-builds` answers `{"enabled": false, "reason": "..."}`.

## HTTP

All routes need a signed-in reviewer, like the rest of `/api`. POSTs are signed reviewer requests.

| Route | Body | Answer |
|:---|:---|:---|
| `GET /api/template-builds` | | `{"enabled": bool, "reason": str or null, "samples": [sample], "builds": [build], "templates": [template]}` |
| `POST /api/template-builds` | `{"sample_id": str}` | `202 {"build": build}`. Starts the run in the background. A second POST for a sample whose build is still running returns that build. |
| `GET /api/template-builds/{build_id}` | | `{"build": build}`. The page polls this about every 700 ms while the build runs. |
| `POST /api/template-builds/{build_id}/approve` | `{"template_sha256": str}` | `{"build": build}`. `409` with `{"detail": sentence}` if a blocking check failed or the hash is not this build's. |
| `POST /api/template-builds/{build_id}/read` | `{"document_id": str}` | `{"reading": reading}`. `409` unless the template is approved. |

### `sample`

```json
{"id": "halcyon-availability-addendum", "title": "Halcyon Grid: Platform Availability Addendum",
 "vendor": "Halcyon Grid Services", "document": {"id": "halcyon-a", "title": "...", "chars": 5120, "text_url": "/fixtures/template_builder_demo/halcyon-a.txt"},
 "next_documents": [{"id": "halcyon-c", "title": "...", "vendor": "...", "chars": 5033, "text_url": "..."}]}
```

### `build`

```json
{"id": "tb_3f9a2c", "sample_id": "halcyon-availability-addendum",
 "state": "QUEUED | CLASSIFYING | READING | BUILDING | CHECKING | READY_FOR_REVIEW | APPROVED | FAILED",
 "started_at": "2026-11-10T13:02:11Z", "updated_at": "...", "finished_at": null,
 "steps": [
  {"id": "classify", "actor": "JEV", "label": "Which contract type is this?", "state": "PENDING | RUNNING | DONE | FAILED | SKIPPED",
   "started_at": null, "finished_at": null, "seconds": null, "model": "jev-1.13.0",
   "summary": "No template on file matches", "detail": {"choice": "unrecognised", "probability": "0.97", "options": ["northwind-cloud-sla", "corvid-ledger-sla", "unrecognised"]}},
  {"id": "reader-1", "actor": "CLAUDE", "label": "Reader 1", "state": "...", "seconds": "11.2", "model": "claude-opus-5-5",
   "summary": "9 terms, 9 quotes found in the contract", "detail": {"terms": 9, "quotes_found": 9}},
  {"id": "reader-2", "actor": "CLAUDE", "label": "Reader 2", "...": "..."},
  {"id": "reader-3", "actor": "CLAUDE", "label": "Reader 3", "...": "..."},
  {"id": "build", "actor": "CLAUDE", "label": "Template builder", "state": "...", "seconds": "14.0", "model": "claude-opus-5-5",
   "summary": "9 extraction rules written", "detail": {"rules": 9, "repair_rounds": 0}},
  {"id": "checks", "actor": "UPTIME", "label": "Checks", "state": "...", "summary": "5 of 5 checks passed", "detail": {}},
  {"id": "review", "actor": "REVIEWER", "label": "Reviewer approval", "state": "PENDING | DONE", "summary": "Waiting for a reviewer", "detail": {}}
 ],
 "terms": [
  {"field": "availability_target_percent", "label": "Availability commitment", "type": "percent",
   "value": "99.95", "display": "99.95%", "quote": "the exact sentence from the contract",
   "readers": [{"reader": 1, "value": "99.95", "quote_found": true}, {"reader": 2, "value": "99.95", "quote_found": true}, {"reader": 3, "value": "99.95", "quote_found": true}],
   "agreement": {"agree": 3, "of": 3},
   "rule": {"pattern": "regular expression source", "group": 1},
   "rule_value": "99.95", "second_document_value": "99.9", "second_document_ok": true,
   "jev": {"yes": true, "probability": "0.98", "model": "jev-1.13.0"},
   "status": "PASS | REVIEW"}
 ],
 "checks": [
  {"id": "quotes", "label": "Every quote is in the contract, word for word", "passed": 27, "total": 27, "ok": true, "blocking": true, "by": "UPTIME"},
  {"id": "agreement", "label": "The three readers agree", "passed": 9, "total": 9, "ok": true, "blocking": false, "by": "UPTIME"},
  {"id": "reproduce", "label": "The template returns every term from this contract", "passed": 9, "total": 9, "ok": true, "blocking": true, "by": "UPTIME"},
  {"id": "second_document", "label": "The template reads a second contract of the same form", "passed": 9, "total": 9, "ok": true, "blocking": true, "by": "UPTIME"},
  {"id": "jev", "label": "Jev: each term is supported by its sentence", "passed": 9, "total": 9, "ok": true, "blocking": false, "by": "JEV", "threshold": "0.90", "lowest": "0.93", "ran": true}
 ],
 "template": {"id": "halcyon-availability-addendum/1", "sha256": "64 hex", "rules": 9, "state": "PROPOSED | APPROVED",
              "approved_by": null, "approved_at": null},
 "error": null}
```

Rules for the shape:

- Money, percentages and probabilities are strings holding decimals. Unknown is `null`, never `0`.
- `steps` always has these seven ids in this order, from the first answer on, so the page can draw the whole run at once.
- `terms` and `checks` are `[]` until their step produces them; `template` is `null` until the builder finishes.
- A `jev` object is present only when Jev really answered. If Jev could not be reached, `classify` is `FAILED` with a
  sentence in `summary`, each term's `jev` is `null`, and the `jev` check has `"ran": false, "ok": false`. The build still
  reaches `READY_FOR_REVIEW`, because Jev's checks are advisory.
- `error` is `{"sentence": "..."}` when `state` is `FAILED`.

### `template` (in the list answer)

`{"id", "sha256", "rules", "state", "approved_by", "approved_at", "sample_id", "vendor", "title"}`

### `reading`

```json
{"document": {"id": "halcyon-c", "title": "...", "vendor": "..."}, "read_by": "TEMPLATE",
 "template": {"id": "halcyon-availability-addendum/1", "sha256": "64 hex"}, "model_calls": 0, "milliseconds": "3.4",
 "terms": [{"field": "availability_target_percent", "label": "Availability commitment", "type": "percent", "value": "99.9", "display": "99.9%", "quote": "the sentence the rule matched"}],
 "found": 9, "total": 9, "read_at": "..."}
```

A term a rule does not find has `"value": null, "display": null, "quote": null`; it is never guessed.

### Additions made by the engine (additive; nothing above was renamed or removed)

- `sample.second_document`: the document used by the second-document check (same shape as `document`).
- `term.rule.map`: present on `choice` terms only (`measurement_period`, `credit_application`): captured phrase
  (lowercase) to option id. `term.rule_quote` and `term.rule_error`: the sentence the rule matched on this contract,
  or why it failed.
- Check `second_document` carries `document: {id, title}`. Check `jev` has `lowest: null` when Jev did not answer.
- The disabled answer also carries `samples: [], builds: [], templates: []`.
- `POST /api/template-builds` answers `429 {"detail": sentence}` after six builds in one server process, and `404`
  for a sample that is not shipped.
- The term set (9): `availability_target_percent`, `measurement_period` (choice), `tier_1_credit_percent`,
  `tier_2_threshold_percent`, `tier_2_credit_percent`, `credit_cap_percent`, `claim_window_days` (integer, days),
  `maintenance_notice_hours` (integer, hours), `credit_application` (choice). See `uptime/template_rules.py`.

## Page (UI agent)

- Agreements page: a section "A contract type Uptime has not read before" listing each `sample`, with one button,
  "Build a reader with Claude agents", that POSTs and goes to `#template-build/<build id>`.
- `#template-build/<id>`: the run, drawn from `build` alone and updated by polling. Actor words on screen: `JEV` is
  "Jev", `CLAUDE` is "Claude", `UPTIME` is "Uptime · fixed rules", `REVIEWER` is "Reviewer".
- After approval the page offers "Read the next contract with the template" for each of the sample's `next_documents`.

## Who owns which files

| Agent | Files |
|:---|:---|
| Engine | `uptime/template_builder.py`, `uptime/template_rules.py`, `fixtures/template_builder_demo/**`, `tests/test_template_builder*.py`, and the wiring lines in `uptime/server.py` and `scripts/setup_northwind.py` |
| Jev | `uptime/jev.py`, `tests/test_jev.py`, `scripts/jev_smoke.py` |
| Page | `web/template_builder_ui.js`, `web/template_builder.test.cjs`, one new block at the end of `web/style.css` (before the side-panel block, which must stay last), the script tag in `web/index.html`, and the route and mount lines in `web/app.js` and the Agreements page |

Each agent appends its own section to `DEMO-CHANGES.md` (changed existing tests by exact name and reason; new files).
