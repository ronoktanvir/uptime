# The demo line of November 10 is merged to `main`

**Date:** November 10, 2026. **Owner of the decision:** Ronok. **Recorded by:** the coordinator (an AI agent).

## Decision

`demo/film-20261110` is merged into `work/submission-integration-20261109` and `main` is fast-forwarded to it, after a full run on the merged commit.

Ronok's words, in order:

- About 03:10 PST: "this is all just for the demo ... I'm doing that to change the rule ... for the next 24 hours, forget about all these rules." He asked for Uptime to interact with Ramp's sandbox and for a separate line without the standing rules.
- About 04:10 PST, through the judge session and confirmed directly: build the template builder for real, rough and narrow, with no prototype label, and show it in the film.
- About 12:10 PST: "can you update the github repo and everything with the demo vid n whatever n new UI and make the read me good".

## What the merge brings

- Bills read from Ramp matched to invoices by vendor, invoice number and amount; fixed notes posted on matched bills through Ramp's API and read back.
- The side panel as a one-bill view; a portfolio page; the steps a decision set off shown one at a time; a second vendor with an estimated credit.
- The template builder: Jev (TypeSafe AI's decision model) for the contract type and for each term against its sentence, three Claude readers in parallel, a Claude-written template stored as data and run by a fixed interpreter, code checks, a reviewer's approval of the exact version.
- The narrated film and its notes.

## What it departs from, and why that is recorded here

Before November 10 the project's rules said Uptime writes nothing to Ramp, the Northwind walkthrough stays apart from Ramp, and every integration merge gets a full run. On the demo line an agent entered vendors, bills and one vendor credit in Ramp's sandbox, Uptime posted notes there, and merges were checked with focused tests. Ronok chose that for the demo. `AGENTS.md` carries a dated note saying the lift was for 24 hours and extends no further. `DEMO-NOTES.md` lists each thing entered in Ramp, by whom and when.

## Alternatives

- **Keep the demo line off `main` and publish only the film.** Rejected by the decision: the film would show features the repository judges clone does not contain.
- **Push the demo line as a branch and leave `main` alone.** Judges clone the default branch; the README would describe code they do not get.
- **Remove the note posting before merging.** It is what the film opens and closes on, and Ronok asked for it.

## Criticism taken before publishing

A read-only review by Claude Opus 5.5 of everything the line adds found nothing that blocked publishing. Acted on before the merge was published:

- Reading `/api/ramp/workspace` could retry a failed note, so a read could write to Ramp. Removed; a timer retries instead, and a test asserts a read posts nothing.
- `ramp_credit` could answer "applied and confirmed" without exactly one credit verified on both sides. It now answers "unknown".
- The sample-contract text route did not check the tenant; the interpreter had no input-size limit. Both added.
- Four sentences in the day's notes contradicted each other or the code. Corrected.

Not acted on: the review noted that the logo lockup's wording in the third-party notices reads as a typo; it quotes the supplied image and was left as written.

## What is not established

- The template builder has run on one contract form with three authored samples that differ only in values. Its accuracy on other wording is unmeasured, and its repair step has run only against stand-ins.
- None of the November 10 work has had an independent acceptance run.
- The film's narration is a synthetic stand-in voice, and nobody has listened to it against the picture.
- No credit is applied in Ramp. Ramp refused to apply the hand-entered vendor credit before the bill has a payment method, and no payment method was set.

## Validation

Full runs on the demo line: `977bd19` (5,539 passed, 3 failed, all from the template builder's new files), then `1ac84fe` (5,543 passed). The merged commit has its own full run; its receipt is in `docs/v4/evidence/submission-20261109/` and its row in the integration table of `docs/v4/submission/COORDINATION.md`.

## Rollback

`main` before the merge was `96e37d7`; the accepted fallback build is `52f1a2f` on `frozen/submission-fallback-20261109`. Rolling back is a revert of the merge commit on `main`, not a forced push. The notes already in Ramp's sandbox stay there either way; they can be deleted in Ramp by hand.
