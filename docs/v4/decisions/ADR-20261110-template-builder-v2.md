# Template builder, version 2: answering a judge's four criticisms

**Date:** November 10, 2026. **Owner of the decision:** Ronok. **Recorded by:** the coordinator (an AI agent).

## Decision

At about 16:55 PST Ronok pasted a review that marked the template builder down on four points and asked for agents to fix them ("can you summon agents to tackle these changes with the github"). Four Claude Opus 5.5 agents worked in separate worktrees from one interface page, `docs/demo/TEMPLATE-BUILDER.md` ("Version 2"); the coordinator joined their work and ran it.

| The review said | What changed |
|:---|:---|
| "The AI and the money never meet" | An accepted read by an approved template produces an agreement in shadow and a credit computed by the existing engine's tier family |
| "Jev changes what the reviewer sees, never what the system does" | Jev's decision routes the run; a term Jev does not support must be acknowledged or approval is refused |
| "It has not read a contract it wasn't written for" | A pasted contract is accepted; the second-contract check uses three fresh readers and no answer key; a held-out evaluation on six forms written blind is published with every run |
| "Reads after approval are the unguarded part" | Ambiguous matches are refused; every read runs five guards; the readers differ in instructions and one in model; each value must be literally in its sentence |

## A change made after measuring

The strict version refused five of six held-out forms, three of them over one term (maintenance notice stated in days or business days where hours were asked). A term every reader agrees the contract does not state is now recorded as not stated, gets no rule and must be acknowledged; no unit is converted and no threshold was changed. With that the engine approved four of six. Because this change was made after seeing the failures on the same six forms, the four-of-six figure is not a clean held-out number for it. All three runs are in `docs/demo/TEMPLATE-BUILDER-HELDOUT.md`.

## Alternatives

- **Leave the strict version.** It is the safest reading of "refuse when unsure", and it returned no wrong value. But it refused whole contract types over a term the credit engine never uses.
- **Convert units** (five days to 120 hours). Rejected: a converted value is not in the contract's sentence, and business days cannot be converted at all.
- **Keep the answer key for the second-contract check.** Rejected: a customer does not have one, and it steered repairs in the first run.

## Criticism not yet answered

- The claim on film is still Northwind's, a contract read by fixed rules. A claim cannot yet be filed from a template-read agreement; that work was started the same evening.
- No real vendor's contract has been through the builder, and the term list is fixed at two credit tiers. That work was also started the same evening.
- On the shipped sample Jev puts two correct terms under its bar on every run. What Jev catches has not been measured; Ronok chose not to measure it now.
- The film shows the first version of the template-builder scene.

## Validation

Focused tests for the template builder, the money link and the Jev client; the JavaScript checks; one real build through the page against the real server (three differing readers, the keyless second-contract check, two acknowledgements, an accepted read, USD 4,200.00 estimated, a pasted contract matched by Jev with no reader started); three runs of the held-out evaluation. The full suite's receipt for the published commit is in `docs/v4/evidence/submission-20261109/`.

## Rollback

`main` before this work was `fa382da`. Rolling back is a revert of the merge commits on `main`, not a forced push. Nothing in this work writes to Ramp.
