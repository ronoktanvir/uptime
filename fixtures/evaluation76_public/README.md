# Public evaluation 76: frozen authored inputs

This package contains exactly **six new fictional vendor agreement/evidence cases and twelve new fictional vendor replies**. Every file is AUTHORED_PUBLIC, contains no customer data, and is authorized for bounded external inference. This is a public authored measurement on a frozen implementation, **not a private or blind holdout**, a human-review benchmark, or evidence of live recovery.

The implementation target is `fd6537cc4e3118a9b6e29f4804a505ed591ea9ea`. Inputs and expectations are frozen before any candidate execution, model proposal, or implementation-owner exposure. The first package commit is the freeze point. No production internals, old frozen control input files, private evaluation files, other implementation branches or actual customer captures were inspected to author these cases. Documentation of public interfaces and limits was read; it contains historical result summaries, which are not independent fresh results.

## Files and oracle

- `inputs/onboarding/` contains six document, overlay and evidence inputs. `inputs/onboarding-index.json` lists the selected monthly or resource profile.
- `inputs/disputes.json` contains twelve replies with synthetic claim context and separately stated supporting facts.
- `expected/onboarding.json` contains the six hand-calculated outcomes and exact amounts. The supported cases cover literal monthly tiers, completed steps, resource interval unions, and a fixed service-month aggregate. Two cases lack determinable governing conditions and require refusal with null money.
- `expected/disputes.json` contains six supported objection/award expectations and six mandatory-review controls. Amounts and monetary conservation are calculated independently of the implementation. Recognizing a vendor-reported award never authorizes a financial mutation.
- `manifest.json` pins every input/expected file and each exact source text. It also pins the complete file-list digest and evaluation policy.

The author did not run an engine or ask a model to generate expected truth. The arithmetic appears alongside the expected values so another reader can check it directly. `SUPPORTED` means that the semantic family appears in the documented scope; it is not a claim that a particular parser will accept every new wording. A failure to extract or compile a supported source is a measured failure, not grounds to relabel that source after seeing results.

## Frozen execution policy

1. Verify the manifest, repository target and all source hashes before execution. Retain inputs/expectations unchanged. Do not tune wording, expectations, parser code or prompts on these results.
2. Have the root integration owner connect these neutral public inputs to existing public CLI/typed interfaces. All adapter mappings, request templates and complete outbound request digests must be fixed before inference. Mapping wire shapes may not supply a missing fact, reinterpret an ambiguous rule or change a financial literal. Report an unrepresentable case as such.
3. Send only each approved `document`/exact source text to the onboarding model. The overlay, evidence, pricing inputs, expected outputs, manual arithmetic and other cases stay outside that request. For disputes use only the one reply's exact text and the minimal synthetic stored-claim context required by the existing public adapter. Do not include supporting-fact findings or expected labels in the model prompt. The public classification is authorization, not evidence of commercial authority.
4. Make at most one call per pinned complete model request. Preserve provider errors, timeouts, malformed JSON, grounding errors, compile refusals and semantic mismatches. No fence removal, output repair, retries, alternate prompts or selective exclusion. Report each stage separately: transport, schema/grounding, source interpretation, expected meaning/arithmetic, and any local downstream execution.
5. Keep all model proposals informational. Any local authority envelopes used by a runner are explicitly scripted and synthetic. No customer runtime enablement, human-approval claim, external vendor communication, Ramp operation, native qualification or financial mutation follows from this measurement.
6. Report exact denominators: six onboarding cases (four documented supported families, two refusal cases) and twelve replies (six supported mappings, six mandatory-review cases). Do not expand the cohort or replace failures. A successful repeated static manifest check is not a second model sample.

The root will integrate the evaluator after the freeze. Runtime outcomes and full integration regression belong in separate receipts; none existed when this package was frozen.

## Documentation consulted

Only public interface/limits documentation was used: `docs/vendor-onboarding.md`, `docs/v4/OPUS56-RESPONSE-GRAMMAR-DISPOSITION.md`, `docs/v4/SOURCE-INTAKE.md`, `docs/v4/GOVERNING-FEE-65A.md`, `docs/v4/OPUS60-INTERPRETATION-RECOMMENDATION.md`, and the interface/limits portions of decisions 70 and 71. No linked prior fixture, review packet, raw proposal, private corpus or implementation source was read for this task.
