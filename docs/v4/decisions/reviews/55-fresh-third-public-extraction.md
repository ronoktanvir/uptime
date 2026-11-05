# Fresh third-source extraction after Opus55 corrections

The fresh genuine extraction was rejected on one source-grounding check. No accepted artifact, candidate, activation or private evaluation resulted. This is a new post-remediation attempt, not the original first-pass extraction.

## Actual invocation and immutable result

The isolated onboarding worktree was fast-forwarded to root integration `07d24c387cc3f91445cbd669ef948441f728626a`. The unchanged application `generate()` flow called actual `claude-opus-5-5` with no tools, strict MCP configuration, no settings sources and no session persistence. Its model-usage identity check succeeded. Only the approved synthetic public source blocks and the reviewed extraction protocol were sent. The call began at `2026-11-05T06:08:32.729872+00:00`.

- Actual model session: `cc7d3b05-2261-48aa-8a75-16903e81050d`
- Historical result: `REJECTED`
- Source text SHA-256: `f9e96913e9abbc341d66ca8a61c619f6619d78b068420fbf88c6a8ccfe1a99d5`
- Raw proposal SHA-256: `2ea482b00048afb105ba4e4460e1922f35d39eca9c0e5e96eee8e9a4298e2bfb`
- New rejected receipt content address: `ea5d0da85701cf81fe9947bc025a905992b507dd8bdc3e3a4d3adb565bc1aa61`
- Prompt SHA-256: `7858e6036b5130996006faee2d38a50857cfe0c7e3baa5fe99a6edd49021e860`
- Public block-input fingerprint: `e3f88f4bfcacdd5c4f5c01f04d5908774c4f53eba044fb8e8c53448f9f098186`
- Compiler semantics revision: `d4a3be3b57880f95cdad3f5c62c8b06e12948ac3e3e821f30414db5125de2f72`

The new create-only receipt is under `$W/tasks/onboarding-third-fresh-07d24c3/rejections/<source-sha256>/<receipt-address>.json`. The same task directory contains `invocation.json`, `result.json`, `offline-diagnostics.json` and the one-attempt wrapper. `$W` denotes the durable engineering workspace. Source JSON and all five original third-source rejection files were hashed before and after the call; all bytes remain unchanged. The source JSON byte hash remains `c330f9bd5b250b8d1429d60cbb0d86fd1b29c33913415155d4b3e1170c46b643`.

## Exact public blocker

Offline diagnostics report only block 13, field `provider_causes`, with `Ungrounded provider_causes labels.` Block 13 has original offsets `[1716,2237)` and SHA-256 `7a653e2ba145dfd2fd7e33ccadef098b80d28e3f3e1b4123f5228008e4e97d32`. The untouched model value contains:

```json
{"label":"provider_incident_unavailable","phrase":"provider incident record marked\nunavailable"}
```

That phrase is an exact contiguous slice of the original approved public block. `_compile_resource` normalizes the block's whitespace before checking stable-label dictionaries with `item['phrase'] in quote`. The original line feed therefore cannot match the normalized block. This failure differs from the previous no-minimum and issuer-authority refusals; the current proposal produces no diagnostic for those blocks.

An independently composed reproduction confirms the comparison defect. The source `Responsibility includes provider equipment\nfailure.` and the exact phrase `provider equipment\nfailure` refuse. Ordinary-space input accepts. Exact CRLF, tab and NBSP phrases also refuse. Conversely, the normalized phrase `provider equipment failure` accepts against that wrapped source. The reproduction log is `label-binding-reproduction.json` in the task directory.

## Bounded correction proposed for root review

Compare the proposed phrase and its current source block using the same existing within-block whitespace normalization, after enforcing the original phrase length, dictionary shape and stable-identifier restrictions. Require a nonempty normalized phrase. Preserve the original phrase, block identity, offsets and source hash. Do not normalize punctuation, combine blocks, invent synonyms or change evidence authority. Independent controls should cover all five list fields, wrapped and unwrapped variants, neighboring-block copying, altered text, unsupported zero-width or hyphen substitutions, and conflicting definitions for a repeated label. Root reserved packet 58 and authorized a public-only independent Opus review before production edits.

No compiler or supported-grammar change is included in this record. Root review is requested before applying the correction. The original model proposal must remain untouched even if offline revalidation later succeeds; a later actual extraction needs separate authorization and its own immutable receipt. Signed candidate/test/shadow execution remains conditional on an accepted genuine proposal, and human interpretation, approval and activation gates remain intact.

The required post-merge `uv run --locked pytest -q` completed with 2,266 passing tests and the existing Starlette/httpx deprecation warning. Its local log is `$W/receipts/onboarding-07d24c3-postmerge.log`.
