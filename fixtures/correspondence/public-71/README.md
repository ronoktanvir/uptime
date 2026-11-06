# Authored public dispute controls 71

These eight new synthetic controls were authored and frozen before implementation. They are development controls, not blind or private evaluation evidence. The model may see source text and scope only; expected reasons stay in the local evaluator. Older failed public and private evaluation results remain unchanged. Runtime customer processing remains disabled.

Frozen controls SHA-256: `16e994d2876a954a4847cab213488a47b5bd8e70c5a5ceaaffb82c1eb42b682f`.

## Recorded public experiment

[Decision 71](../../../docs/v4/decisions/ADR-0071-source-locked-dispute-proposals.md) distinguishes the initial and revised requests. [The complete public receipt](../../../docs/v4/evidence/disputes-71-public.json) preserves both requests and responses, exact model/session identifiers, stream hashes, mapping outcomes and refusals. The first batch had 5/8 structurally compatible responses and 0/3 supported positive mappings. The revised `source_blocks_v2` batch had 8/8 structurally compatible responses, 3/3 supported positive mappings and 5/5 negative UNKNOWN mappings. Neither batch evaluated actual human review or operational compatibility.

To explicitly reproduce the current authored experiment with the installed authenticated CLI, choose a new output directory:

```sh
uv run --locked python scripts/propose_correspondence_blocks_public_71.py --execute-public --output /tmp/uptime-public-71-new
```

This makes eight separately manifested public-only calls, each bounded to 60 seconds, 300000 output bytes and a client-reported USD 1 budget setting (not a hard cost cap). Use `--case deadline-paraphrase` to select one frozen control. No customer data or private evaluator input is accepted. Existing output directories are refused before dispatch. Omitting `--execute-public` refuses inference. The CLI schema mode is not used because its actual probe exposed a tool call.
