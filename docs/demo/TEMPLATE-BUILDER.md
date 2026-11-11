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

Every route needs a signed-in account, like the rest of `/api`: the GET routes and the sample text accept any signed-in account of the tenant, and the POSTs are signed reviewer requests.

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

# Version 2: answering four criticisms (November 10, afternoon)

A judge's review marked the first version down on four points. This section is the contract for the four agents
fixing them in parallel. Where it differs from the text above, this section wins. Everything not mentioned stays.

| # | Criticism | What changes |
|:--|:---|:---|
| 1 | "The AI and the money never meet": an approved template's read returns nine terms and stops | An accepted read creates an agreement and an estimated credit computed by the existing deterministic engine, listed on the portfolio |
| 2 | "Jev changes what the reviewer sees, never what the system does" | Jev's decision routes the run, and a term Jev does not support blocks approval until the reviewer acknowledges it |
| 3 | "It has not read a contract it wasn't written for": shipped samples only, one form, an answer key | A pasted contract is accepted; the second-contract check needs no answer key; a held-out evaluation on contracts written blind is run and published whatever it scores |
| 4 | "Reads after approval are the unguarded part"; same model and prompt show consistency, not correctness | Ambiguous matches are refused; every read is guarded; readers differ in instructions and model; each value must be in its sentence |

## The run, version 2

1. **Jev routes.** The `choice` is among the APPROVED templates in this workspace plus `unrecognised`.
   - Jev picks an approved template with probability at least `0.80`: **no reader starts.** The contract is read by that
     template under the read guards below. Build state `MATCHED`; steps `reader-1..3` and `build` are `SKIPPED` with the
     summary "Not started: Jev matched an approved template"; `checks` holds the read guards; `review` is `SKIPPED`.
   - Jev answers `unrecognised`, or anything under `0.80`: the readers start, as before.
   - Jev cannot be reached: **nothing starts.** Build state `NEEDS_REVIEWER`. A reviewer may press "Build without Jev"
     (`POST /api/template-builds/{id}/continue`, body `{}`), which is recorded on the `classify` step as a reviewer decision.
2. **Three readers that differ.** `reader-1` reads clause by clause (claude-opus-5-5). `reader-2` lists every number in the
   contract and what it governs, then the terms (claude-opus-5-5). `reader-3` is the sceptic: for each term it looks for a
   second place that states it and reports a conflict (claude-sonnet-5-5, a different model). Each step's `model` is the
   model that really answered, and `detail.role` is one of `clause_by_clause`, `numbers_first`, `sceptic`.
3. **The builder**, as before.
4. **Checks.** Ids in this order:
   - `quotes` (blocking): every quote is in the contract, word for word.
   - `value_in_sentence` (blocking, new): each term's value is literally in its quoted sentence, as digits or as number
     words. Code, no model.
   - `agreement` (advisory): the three readers agree.
   - `reproduce` (blocking): the template returns every term from this contract, each matched exactly once.
   - `second_document` (blocking when a second contract was given): **no answer key.** Three fresh readers read the second
     contract; the template's value for each term there must equal what those readers agreed on. With no second contract
     the check has `"ran": false, "ok": false, "blocking": false` and the template can still be approved; the page says it
     was not checked on a second contract.
   - `jev` (now gating): a term Jev answers "no" to, or under `0.90`, or does not answer, gets `"needs_acknowledgement": true`.
5. **Approval.** `POST .../approve` body is `{"template_sha256": str, "acknowledged": [field, ...]}`. It answers `409` unless
   `acknowledged` names exactly the terms with `needs_acknowledgement`. The `review` step's detail records them.
6. **Reads are guarded.** `POST .../read`, and the `MATCHED` route, run these guards; a read that fails any has
   `"status": "REFUSED"`, lists why, and feeds nothing downstream:
   - `complete`: every rule found a value.
   - `unambiguous`: no rule matched in more than one place with different values. (The interpreter itself refuses these.)
   - `value_in_sentence`: each value is in the sentence its rule matched.
   - `plausible`: percentages within 0 to 100, the second tier's threshold below the commitment, the second tier's credit
     above the first, the cap not below the highest credit, days and hours positive.
   - `template_match` (advisory when Jev cannot be reached): Jev chooses this template for the document at `0.80` or more.

## Shapes, version 2

`POST /api/template-builds` accepts either `{"sample_id": str}` or a pasted contract:

```json
{"contract": {"title": "…", "vendor": "…", "text": "… up to 60,000 characters …"},
 "second_contract": {"title": "…", "text": "…"},
 "consent": true}
```

`second_contract` may be `null`. `consent` must be `true`: the page says the text will be sent to Claude and to Jev.
A pasted contract is stored only in the workspace's `template-builds/` folder.

`build` gains:

```json
{"state": "… | MATCHED | NEEDS_REVIEWER",
 "source": {"kind": "sample | pasted", "title": "…", "vendor": "…", "chars": 6077},
 "second": {"provided": true, "title": "…"},
 "matched_template": {"id": "…", "sha256": "…", "probability": "0.93"},
 "readings": [reading]}
```

`sample_id` is `null` for a pasted contract. `matched_template` is `null` unless the state is `MATCHED`.

A `term` gains `"value_in_sentence": true`, `"needs_acknowledgement": false`, and
`"second_readers": {"agree": 3, "of": 3, "value": "99.9"}` (or `null` with no second contract). `second_document_ok` now
means the template's value there equals `second_readers.value`.

A `reading` gains:

```json
{"id": "rd_4be1", "status": "ACCEPTED | REFUSED",
 "guards": [{"id": "complete", "label": "Every rule found a value", "ok": true, "detail": "9 of 9"},
            {"id": "unambiguous", "label": "…", "ok": true, "detail": null},
            {"id": "value_in_sentence", "label": "…", "ok": true, "detail": "9 of 9"},
            {"id": "plausible", "label": "…", "ok": true, "detail": null},
            {"id": "template_match", "label": "Jev: this document follows the template", "ok": true, "detail": "0.94", "advisory": false}],
 "jev_template": {"choice": "…", "probability": "0.94", "model": "jev-1.13.0"},
 "agreement": null}
```

`model_calls` stays the number of calls that produced the values, which is `0`; a Jev guard call is reported under
`jev_template`, and the page says "values by fixed rules; Jev checked the document type".

`reading.agreement` is filled by the money link (below), or stays `null`.

## Python, version 2

- `uptime/template_rules.py`: `apply` finds every match of a rule. More than one match with different values gives
  `value: null` and an `error` naming how many places matched; identical values in several places are accepted.
  New: `value_in_sentence(field, value, sentence) -> bool`, `plausibility(values: dict) -> list[str]` (empty when plausible).
- `uptime/template_builder.py`: `TemplateBuilds.approved_readings()` returns, for every ACCEPTED reading under an APPROVED
  template in this workspace:

```python
{"build_id": str, "reading_id": str, "template": {"id": str, "sha256": str},
 "vendor": str, "document": {"id": str, "title": str, "customer": str | None},
 "values": {field: value_string_or_None}, "read_at": iso}
```

  It also exposes `set_agreement(build_id, reading_id, agreement: dict)` so the money link can attach its result, which
  the page shows.

## The money link (criticism 1)

`uptime/template_agreements.py` (new) turns one entry of `approved_readings()` into an agreement in the shape the existing
credit engine evaluates, and evaluates one authored service month for it. The model is not involved: terms came from the
approved template's read, and the arithmetic is the engine's. The result is attached to the reading:

```json
{"agreement_id": "HGS-PAA-2026-0518", "state": "SHADOW", "read_by": "template:halcyon-availability-addendum/1",
 "month": "2026-10", "availability_percent": "99.41", "credit_percent": "25", "monthly_fee": "8000.00",
 "credit": {"amount": "2000.00", "currency": "USD", "stage": "ESTIMATED"},
 "inputs": [{"label": "…", "value": "…"}], "evaluation": "…one sentence, the engine's own…"}
```

and listed in the workflow view's `opportunities` in the same shape Corvid's entry has, with
`"agreement": {"id": …, "read_by": "template:<template id>", …}` and `"source": "template"`. A read with no usage evidence on
file (a pasted contract) gets an agreement with `"credit": null` and `"evaluation": "Needs usage evidence"`.
Unknown stays null. Nothing here is posted, claimed or applied.

## Who owns which files, version 2

| Agent | Files |
|:---|:---|
| Engine | `uptime/template_builder.py`, `uptime/template_rules.py`, `tests/test_template_builder*.py`, `scripts/template_builder_smoke.py` |
| Money link | `uptime/template_agreements.py` (new), `uptime/demo_opportunities.py`, `fixtures/template_builder_demo/evidence/**` (new), `tests/test_template_agreements.py` (new) |
| Held-out evaluation | `scripts/evaluate_template_builder.py` (new), `fixtures/template_builder_heldout/**` (new), `docs/demo/TEMPLATE-BUILDER-HELDOUT.md` (new) |
| Page | `web/template_builder_ui.js`, `web/template_builder.test.cjs`, its block in `web/style.css`, and the one line in `web/workspace_ui.js` or `web/ramp_ui.js` that words `read_by` when it starts with `template:` |

Each agent appends its own section to `DEMO-CHANGES.md`: changed existing tests by exact name and reason, and new files.
