# Template builder: held-out evaluation

A judge's review said of the template builder: "It has not read a contract it wasn't written for." This page records
what happened when it was given contracts it was not written for: six contract forms written by fresh Claude calls
that never saw the builder, one build per form, and a read of a third, held-out contract of each form with the
template that build produced. The result is published as it came out. Nothing in the engine, its prompts or its
samples was changed for this evaluation.

## Three runs, side by side

The same six frozen forms were run three times on November 10, 2026, each time on a different state of the engine.
The first run is the baseline described in the rest of this page. The other two were added by the coordinator after
the engine changed. All three are kept, including the one that scored worst.

| Run | Engine | Forms that passed every blocking check | Held-out contract C: terms scored | Correct | Wrong | Left unread | Not stated |
|:---|:---|:---|:---|:---|:---|:---|:---|
| 1 | Version 1. Its second-contract check was given a hand-written answer key for contract B | 5 of 6 | 45 (five forms read) | 36 | 0 | 4 | 5 |
| 2 | Version 2, strict: no answer key (three fresh readers read B), each value must be in its sentence, all nine terms required | 1 of 6 | 9 (one form read) | 9 | 0 | 0 | 0 |
| 3 | Version 2, with terms every reader agrees the contract does not state | 4 of 6 | 36 (four forms read; one of those reads was refused whole by the read guards) | 25 | 0 | 8 | 3 |

Results files, in order: `20261111T010416Z.json`, `20261111T011557Z.json`, `20261111T012703Z.json` under
`fixtures/template_builder_heldout/results/`. A run between the first and second measured nothing because of a fault
in the evaluation script and is kept apart in `results/harness-fault/` with a note.

**No run returned a wrong value.** Every miss was a blank or a refusal.

**Why run 2 fell to 1 of 6.** Version 2 required all nine terms and required each value to be literally in its
sentence. Five of the six forms state scheduled-maintenance notice in days or Business Days, not hours. Their readers
returned nothing for that term (or, on one form, 120 converted from "5 days"), and that one term blocked the whole
template. Three forms failed on that term alone, one on it and one other term, and one on it and two others.

**What changed for run 3.** A term that every reader agrees the contract does not state, in the unit asked, is
recorded as not stated. It gets no rule, the reviewer must acknowledge it before approval, and no unit is converted.
Checks and thresholds for stated terms were not changed. The availability commitment and the first-tier credit must
still be stated.

**Run 3, form by form.**

| Form | Author model | Build | Held-out contract C |
|:---|:---|:---|:---|
| 1 | Opus 5.5 | Passed. 3 terms flagged by Jev for the reviewer | Accepted. 9 of 9 correct |
| 2 | Sonnet 5.5 | **Refused** at `second_document`: contract A gives notice in Business Days, so the term is not stated in hours, but contract B states 72 hours. The author changed units between documents | Not read |
| 3 | Haiku 5.5 | Passed. 4 terms to acknowledge | **Read refused** by the `complete` guard: 6 of 8 rules found a value. The author rewrote clauses between documents. Scored as 7 unread, 2 not stated |
| 4 | Opus 5.5 | Passed. 2 terms to acknowledge | Accepted. 8 of 8 correct, 1 not stated |
| 5 | Sonnet 5.5 | Passed. 3 terms to acknowledge | Accepted. 8 correct, 1 unread: the key counts "5 days" as 120 hours, and the template does not convert units |
| 6 | Haiku 5.5 | **Refused** at `value_in_sentence`, `reproduce` and `second_document`: the measurement period is defined by reference ("Service Period"), and the cap runs over twelve months, not as a percentage of the month | Not read |

Run 3 used 48 Claude calls and 48 Jev calls in 214.7 seconds. Every form had at least two terms the reviewer must
acknowledge, and a script made those acknowledgements and approvals, not a person.

**What these three runs do not establish.** They are one run each on six forms. The contracts were written by Claude
models, as the readers are, from briefs the evaluation's author wrote after seeing the builder's term list. None is a
real vendor's contract. Run 3's change was made after seeing run 2's failures, on these same six forms, so run 3 is
not a clean held-out number for that change: a fresh set of forms would be.

Rerun with one command and no arguments:

```
uv run --locked python scripts/evaluate_template_builder.py
```

Baseline result file: `fixtures/template_builder_heldout/results/20261111T010416Z.json` (engine at `04d9ee1`, which
is the version 1 engine described in the first part of `docs/demo/TEMPLATE-BUILDER.md`).

## How the contracts were written and frozen

- **Brief.** `fixtures/template_builder_heldout/briefs/common.md` asks for a realistic availability addendum, schedule
  or rider for a fictional vendor and customers, stating an uptime commitment, how and over what period it is measured,
  credits in two tiers, a cap, a claim deadline, scheduled-maintenance notice and how a credit is paid, plus the other
  ordinary provisions such a document carries. It asks for three documents of the same form (A, B, C) with different
  parties and numbers, and, separately, a JSON record of the values the author wrote, in a structure of the author's
  choosing. Each form adds one style brief (`style-1.md` to `style-6.md`); the exact text sent is `briefs/form-<n>.md`.
  The briefs contain none of the builder's field names, prompts, rules, the shipped Halcyon samples or their wording.
- **Authors.** One fresh Claude Code CLI call per form, with the product's safe invocation (`-p --safe-mode --tools ''
  --strict-mcp-config --setting-sources '' --no-session-persistence --output-format json`, empty temporary directory),
  run by `fixtures/template_builder_heldout/author.py`. Each model was first checked with one tiny call; all three were
  accepted.

  | Form | Style | Author model | Seconds | A / B / C characters |
  |:--|:--|:--|--:|:--|
  | form-1 | Formal US law-firm drafting | claude-opus-5-5 | 146.8 | 13,140 / 13,148 / 13,200 |
  | form-2 | Plain-English startup terms ("we", "you") | claude-sonnet-5-5 | 68.7 | 5,223 / 5,196 / 5,195 |
  | form-3 | Schedule with a plain-text table of thresholds | claude-haiku-5-5 | 52.2 | 8,101 / 8,181 / 7,788 |
  | form-4 | Numbered definitions first, operative clauses later | claude-opus-5-5 | 136.0 | 10,382 / 10,406 / 10,415 |
  | form-5 | Short order-form rider | claude-sonnet-5-5 | 49.9 | 3,433 / 3,429 / 3,431 |
  | form-6 | British drafting, "service level rebate" | claude-haiku-5-5 | 96.7 | 10,608 / 10,610 / 10,608 |

- **Freezing.** Each answer is saved as returned (`forms/form-<n>/response.txt`); `a.txt`, `b.txt` and `c.txt` are the
  text between its markers with surrounding newlines removed; `manifest.json` records the model that answered, the
  brief file and its SHA-256, the time and the SHA-256 of every file. The evaluation script refuses to run if a
  document no longer matches its hash. No contract was edited. No author output was unusable, so nothing was
  discarded and no replacement was asked for.
- **What the authors did with "the same form".** The opus and sonnet forms (1, 2, 4, 5) and the haiku form 6 keep one
  wording and change parties and numbers (12 to 19 changed lines between A and C). Form 3 (haiku) rewrote about a
  third of its lines between documents. Forms 3, 5 and 6 changed the vendor as well as the customer. Several forms
  changed more than numbers between documents: form 2 states maintenance notice as "5 Business Days" in A, "72 hours"
  in B and "10 days" in C, measures C by calendar quarter, and pays the credit three different ways; forms 3, 5 and 6
  measure B by calendar quarter; form 3's C measures availability over "each rolling period of thirty (30)
  consecutive days". These are what the authors wrote; they were kept.
- **The key.** I (the evaluating agent, Claude Opus 5.5 in Claude Code) mapped each author's stated values onto the
  builder's nine terms by hand, in `forms/form-<n>/key.json`, reading the contract to settle anything unclear. I had
  read the builder's term list (`uptime/template_rules.py`, `TERMS`) before writing it. The product never sees the
  key. Mapping decisions that matter for the score:
  - Maintenance notice stated in **Business Days** (form 2 A; all of forms 3, 4 and 6) has no fixed number of hours, so
    the term, an integer number of hours, is `not_stated`. Notice stated in calendar **days** (form 2 C; form 5) is
    keyed as days × 24 (for example "at least 10 days' notice" is `240`).
  - Form 6 caps rebates per "Measurement Period", which that form defines as each twelve-month period, while
    availability is measured per "Service Period" (a month or quarter). The term means a cap per availability period,
    which the contract does not state, so `credit_cap_percent` is `not_stated` for form 6.
  - Form 3 C's rolling 30-day period is none of the term's options, so `measurement_period` is `not_stated` there.
  - Form 2 B ("pay it to you as a refund by bank transfer") and C ("pay it back to the card or account you used to pay
    your fees ... We won't make you wait for your next invoice") are `refund`. Form 3 B (a credit note the customer may
    set off against the next invoice, otherwise a transfer) is `next_invoice`.

### What "blind" does and does not mean here

- The authors never saw the builder, its prompts, its rules, its term names or the shipped samples. In that sense the
  contracts were written blind.
- The authors are Claude models, and so are the builder's readers and template writer. Contracts written by one model
  family and read by the same family may share habits of phrasing that real contracts do not.
- I wrote the seven-item brief and the six style briefs, after reading the builder's documentation. The brief's list
  of what to state follows the builder's nine terms closely, because the task required it; real addenda often omit
  some of them or state them in other ways.
- I wrote the key, having seen the term list. Where a contract's wording did not fit a term, I chose the mapping
  above; another reader could choose differently (for example, accept form 6's annual cap).
- **The version 1 engine's second-contract check needs an answer key.** For the baseline it was given my key for B.
  The builder never sees that key, but when a rule fails on B the repair prompt says so, so the key steers the repair
  rounds. Forms 2, 3 and 5 used repair rounds.

## Run 1 in detail: the baseline (version 1 engine)

As printed by the script:

```
Held-out evaluation, engine API version 1 (04d9ee11c7f717e0cfb23b3a847bc642b86f603c). Approvals were made by a script (evaluation-script), not a person.
Version 1: the second-contract check is given the hand-written key for B as its answer key, because that API needs one.
form    author             build             blocking failed  approved flagged C read           ok wrong  ref  n/s    secs claude  jev
--------------------------------------------------------------------------------------------------------------------------------------
form-1  opus-5-5           READY_FOR_REVIEW  -                script   3       no status (ver    9    0    0    0    32.0      4   10
form-2  sonnet-5-5         READY_FOR_REVIEW  -                script   2       no status (ver    6    0    3    0    28.7      5    9
form-3  haiku-5-5          READY_FOR_REVIEW  -                script   3       no status (ver    6    0    1    2    37.3      5    9
form-4  opus-5-5           READY_FOR_REVIEW  -                script   4       no status (ver    8    0    0    1    31.1      4    9
form-5  sonnet-5-5         READY_FOR_REVIEW  reproduce,second_document no       4       not read          -    -    -    -    36.5      6   10
form-6  haiku-5-5          READY_FOR_REVIEW  -                script   5       no status (ver    7    0    0    2    34.2      4    8

forms: 6; all blocking checks passed: 5; approved by the script: 5; forms with a term flagged for the reviewer: 6
held-out C: 5 forms read (0 reads refused); of 45 terms scored: 36 correct, 0 wrong, 4 refused, 5 not stated
```

- **Builds.** Of 6 forms, **5** built a template that passed every blocking check. The script approved those 5 under
  the name `evaluation-script`; no person reviewed them. Every one of the 6 builds had at least one term marked
  `REVIEW` for a reviewer (2 to 5 terms per form; see below).
- **Held-out reads.** C was read for the 5 approved forms: 45 terms scored, **36 correct, 0 wrong, 4 refused, 5 not
  stated** (the key says the contract does not state the term and the read returned nothing). Of the 40 terms the key
  says C states, 36 were read correctly and 4 were not read. Form 5's 9 terms on C were not read, because its template
  was not approved; they are not in these counts.
- **Wrong values: none.** No read returned a value that differs from the key, and no read returned a value for a term
  the key marks not stated. The version 1 read has no guards, so this is the interpreter's own behaviour: a rule that
  does not match returns nothing.

### The four refused terms

| Form | Term | Key | C's sentence | Why the template returned nothing |
|:--|:--|:--|:--|:--|
| form-2 | measurement_period | calendar_quarter | "- Measurement Period: each calendar quarter during the term." | The rule captures "calendar quarter", but its map lists only "calendar month" and "month" (A and B are both monthly), so the captured phrase is not an option. |
| form-2 | maintenance_notice_hours | 240 | "We'll give you at least 10 days' notice of Scheduled Maintenance, by email to your account administrator." | The rule reads only "at least (N) hours' notice" (B's wording); C states days. |
| form-2 | credit_application | refund | "Once we've confirmed a credit, we'll pay it back to the card or account you used to pay your fees, within 45 days of confirming it." | The rule looks for "next invoice", "refund" or "bank transfer" after "confirmed a credit, we'll"; C uses none. |
| form-3 | credit_application | next_invoice | "7.1 The Vendor shall deliver each validated Service Credit to the Customer as a credit memo applied against the next invoice issued under the Master Agreement." | The rule is anchored on A's and B's wording ("apply each validated Service Credit as a credit", "set off the credit note"); C's wording differs. |

Three of the four come from form 2, the form whose author changed units and payment wording between documents, and the
fourth from form 3, the form whose author rewrote clauses between documents. Where the held-out document kept the
form's wording, every stated term was read correctly.

### The form that did not pass (form 5)

Form 5 states notice as "at least 5 days' written notice" (B: 7 days). The three readers agreed on `120` (hours),
correctly converting days to hours, but a rule can only capture text from the contract; it cannot multiply. The
template returned nothing for the term on A and B, so `reproduce` and `second_document` failed (8 of 9 each) and the
template could not be approved. The second repair round failed with "The builder's answer did not have exactly one rule
per requested term." For diagnosis only (not counted above), the script ran the unapproved template on form 5's C: 8
of 9 correct, 0 wrong, 1 refused (the notice).

### Terms flagged for the reviewer

`REVIEW` came from two sources. Terms with no value (Business-Day notice; form 6's cap) are always `REVIEW`. The rest
were Jev answering "no" or below 0.90 about a sentence that does support the value: for example Jev answered "no"
for the second tier's threshold in forms 1 (0.07), 4 (0.11) and 6 (0.04), each of which the readers, the template and
the key agree on. In version 1 Jev is advisory, so these did not block approval.

## Time and calls

| Form | Build seconds | Claude calls | Jev calls | Repair rounds |
|:--|--:|--:|--:|--:|
| form-1 | 32.0 | 4 | 10 | 0 |
| form-2 | 28.7 | 5 | 9 | 1 |
| form-3 | 37.3 | 5 | 9 | 1 |
| form-4 | 31.1 | 4 | 9 | 0 |
| form-5 | 36.5 | 6 | 10 | 2 (second failed) |
| form-6 | 34.2 | 4 | 8 | 0 |
| **All** | **199.8** | **28** | **55** | |

Approval took under 10 ms and each read of C under 5 ms, with no model call. Claude calls for the whole exercise:
3 model checks, 6 author calls and 28 build calls (37). No Claude call failed.

## What this does not establish

- **Six forms, one run each.** Model output varies between runs; a second run could build a different template and
  score differently. No variance was measured.
- **Authored, not real.** The contracts were written for this test from a brief that lists exactly the builder's
  terms. Real contracts arrive as scans and PDFs, omit or bury terms, amend each other and use units and structures
  the brief did not invite.
- **One author family.** Every author was a Claude model, as are the builder's readers.
- **My key and my briefs.** I wrote both, after reading the builder's term list; the mapping choices above affect the
  counts.
- **The baseline second-contract check used my key for B.** The version 2 engine's keyless check has not been
  measured here.
- **A script approved the templates.** No person reviewed any build.
- **Version 1 reads are unguarded.** "0 wrong" is the interpreter's own behaviour on these 5 documents, not the effect
  of version 2's read guards.

## Running it again on version 2

The script uses version 2 when `TemplateBuilds.start` accepts `contract`: it passes A as a pasted contract with B as
`second_contract` and `consent=True` (no answer key), and approves with `acknowledged` naming exactly the terms marked
`needs_acknowledgement`. The version 2 interface does not say how an approved template reads a pasted document. If
`read` accepts `contract` or `text`, the script uses it; otherwise it runs the approved template through
`template_rules.apply` and the version 2 guard functions (`value_in_sentence`, `plausibility`) itself, without Jev's
`template_match` guard, and records that path in the results. A read with `status: REFUSED` counts all its terms as
refused.
