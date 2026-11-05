# Independent Gates 2 and 3 acceptance

Status: **PRIVATE ACCEPTANCE NOT RUN HERE**. Neither gate is certified. Root owns actual fixture execution and external model transport. Harness validation: **20 tests passed** using the shared runtime; the two API-oriented harness tests use an in-process listener substitute and do not claim a real-loopback acceptance pass.

The independent fixture was frozen at `9364cd2bf2023adbc1a6f99bc275ac1ae36476ee` before product inspection. The QA worktree started from `940cd45`. Ownership is limited to this document, `scripts/blind_acceptance.py`, and `tests/test_blind_acceptance.py`; product behavior and frozen inputs are not edited here.

Private synthetic records stay in shell-local memory and disposable local databases. Exported receipts contain hashes, counts, feature categories, fail codes and expected/observed money only. Neither exception text nor HTTP bodies are exported. Gold comparison follows observation capture. Missing execution, unknown amounts and numerically wrong amounts remain distinct.

Execution must use real signed loopback HTTP, normal vendor intake and independently signed inbox sources. The source checkout is selected with `--source`. Public model extraction is supplied by the root operator through `UPTIME_PUBLIC_EXTRACTIONS`; `UPTIME_MODEL_PROPOSITIONS=1` is explicitly authorized. This runner does not invoke a model or construct extraction proposals.

The frozen interchange stores case input selectors together with expected results. Input-only projection requires the operator's authorization or a separately supplied input plan. The projection scanner decodes selector values only and skips expected-result value tokens; the expected-result JSON is decoded only after observations exist.

A rejected or unavailable public extraction blocks contract acceptance. A separate denial exercise against a previously supported general adapter can establish dispute generality only; it cannot make unsupported frozen terms active or turn unavailable money into agreement.

## Reproduction

The runner is independent of the product checkout selected by `--source`. Run it in a fresh interpreter with the shared runtime. This command's `--allow-input-projection` explicitly authorizes projection of case selectors from the combined fixture file; it does not authorize using expected outcomes during execution.

```sh
UPTIME_PUBLIC_EXTRACTIONS=/Users/ronoktanvir/.local/share/uptime-engineering/review/extractions \
UPTIME_MODEL_PROPOSITIONS=1 \
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python \
  /Users/ronoktanvir/.local/share/uptime-engineering/worktrees/blindrun/scripts/blind_acceptance.py \
  --source /Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4 \
  --fixture-root /Users/ronoktanvir/.local/share/uptime-engineering/worktrees/blind/fixtures/fresh-blind \
  --receipt /Users/ronoktanvir/.local/share/uptime-engineering/tasks/blind-acceptance-01.json \
  --allow-input-projection
```

Alternatively provide `--input-plan` containing `fixture_manifest_sha256` and a `cases` list with only `id`, `as_of`, optional account/resource/month selectors, `input_artifact_ids`, and `input_correspondence_ids`. The plan must bind the exact manifest. Each rerun requires a new receipt path; the runner refuses to overwrite an earlier receipt. Receipt files use mode `0600`.

The default manifest pin is the initial seven-case freeze. Additive boundary files are not implicitly included. Another external fixture using the published `fresh-blind-1` interchange must supply its own explicit `--manifest-sha256`; filenames, customer names and vendor names do not select logic. Unsupported schema or expected-result fields fail explicitly. An arbitrary JSON corpus is not silently treated as this interchange.

Exit `0` requires both gates; exit `1` records incomplete or failing acceptance; exit `2` means the receipt could not be safely created. Source changes during execution, fixture hash changes, missing cases, unknown expectation fields, missing runtime capabilities and unavailable calculations block acceptance. The stdout summary contains only counts, hashes and failure codes.

## What the runner exercises

Each case uses a disposable database and a real numeric loopback listener. A `ReviewerClient` signs normal vendor intake and case operations. Inbound sources use independent keys and exact scope grants when the selected product supports the grant interface; the earlier HMAC interface retains separate role/account bindings. An audit hook rejects nonlocal connections, DNS lookups and non-Git subprocesses. Product output is discarded at the descriptor layer, so HTTP bodies and private exception messages never enter logs.

Only explicitly selected evidence available by the case's `as_of` enters execution. Evidence and correspondence are merged into their original arrival order. A provider record without a resource retains that missing resource. An incident does not become a complete monthly report. Historical filing and supplement receipts retain their original kind and time; the runner does not convert them into new approvals or generic scoped attachments. Unsupported records reach signed schema validation and their refusals remain visible as failure counts.

When the candidate is quarantined, the runner attempts inactive evaluation and the no-ready inbox denial. It then separately replays available frozen correspondence against a preexisting general control read from `940cd45:tests/test_v4_routes_integration.py`. This control uses its own original agreement, observations, filing time and expected amount, with local diagnostic account/resource binding. Frozen message text and arrival time are unchanged. The control's source hash and results stay separate; its amount never supplies a holdout result. A successful HTTP delivery alone does not establish correct denial reasoning.

The runner seals observed summaries before opening expected-result fields. Comparison exports expected/observed money, outcome categories and hashed field identifiers. Unknown money stays null; unavailable execution stays `UNAVAILABLE`; a numerical disagreement is `WRONG_MONEY`. Unmapped assertions are counted individually. Candidate-generated tests never supply the oracle.

## Remaining implementation boundaries

These are concrete interface gaps identified by source inspection, not private acceptance results:

- `correspondence_types.py` and `correspondence_resource.py` need source-authenticated representations for provider resource mapping, billing allocation, signed discounts and previously issued credit. The runner preserves these fields instead of dropping them to satisfy a narrower invoice schema.
- Historical filing and supplement intake needs a verified original receipt clock and original channel. Prospective `filing_material` and an unfiled message cannot establish that historical submission occurred.
- Complete-month assertions need explicit evidence. The translator cannot infer a complete month from individual incidents or manufacture customer cause attestations from provider records.
- A newly accepted extraction still needs a separately authored promotion suite and, where applicable, interpretation review. The current runner does not create a positive activation suite from holdout gold. It reports `INDEPENDENT_PROMOTION_SUITE_REQUIRED` and leaves the candidate in shadow.
- Exact expected-result fields that have no observation mapping remain `EXPECTATION_UNMAPPED` or `TERM_EXPECTATION_UNMAPPED`. Extending the comparison requires a documented field mapping; changing or ignoring gold is not an acceptable fix.

The post-freeze evaluator addendum describes maintenance, prior-credit, after-discount fee and supplement fields. It does not establish that the signed inbox currently transports those fields or that the private corpus supplies every required attestation. Those boundaries must be checked on the actual source used by root, followed by a fresh receipt after real changes.
