# ADR-0025: Open contract propositions

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Allow tool-free typed clause proposals grounded in exact public-source spans, but require material coverage, bounded primitives, finite customer coverage and separate interpretation/activation.

Strict grammar is safer but rejects ordinary prose; asking customers to rewrite terms into DSL fails the ingestion objective. Arbitrary confident model output cannot establish meaning. Human-authored rules remain a slower fallback, not evidence of autonomous extraction.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/25-open-contract-propositions.json](reviews/25-open-contract-propositions.json); its sanitized input is [packets/25-open-contract-propositions.md](packets/25-open-contract-propositions.md). Receipt time: `2026-11-05T00:21:00.189705+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `024cc548-b0dc-4c03-b181-8c65c83ab4b0`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus’s decisive objection is complement coverage: exact quotations do not prove omitted exceptions or definitions were handled. It demands unbound-text review, mutation/paraphrase tests and explicit source/supersession provenance.

**Root position and reconciliation:** Accept this distinction: a matching span is evidence of text, not proof of semantic completeness. Public effective_until=null means no observed end in that version; it must not imply perpetual customer entitlement. Private overlays remain outside external model inputs. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

vendor_terms.compile_propositions and resource terms constrain operators; candidate digests include overlay and source extraction. Overlay requires explicit effective coverage and optional governing evidence. Unsupported material clauses must block operational use; general coverage has not been established here.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/vendor_terms.py](../../../uptime/vendor_terms.py)
- [uptime/vendor_model.py](../../../uptime/vendor_model.py)
- [uptime/vendor_resource_terms.py](../../../uptime/vendor_resource_terms.py)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_vendor_rejections.py tests/test_vendor_resource.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Dropping an exception, flipping a comparator or hiding an incorporated definition while retaining eligibility falsifies validation. A positive hand-tuned replay does not close unseen generalization.

## Versioned rollback

Quarantine the candidate and revoke active dispatch; retain source bytes and failed interpretation. A changed compiler/source requires a new digest, independent regression and fresh approval rather than editing prior artifacts. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `cd3e061db65d7f76a0b4e2fb1bfe3c4866f732356edebe20e280107ee72cf858` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `729da6ac68d622236d6d5ba2c59e4ad8fafda631e284a72cf79e7619d58f6a78`.
- Review-prompt SHA-256 recorded by receipt: `7056ffc0bcee3cfe383ad8e14606c89ee99d661c020984ab98374fd3261d98b2` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
