# ADR 0070 — Public completed-step proposal representation

The existing monthly compiler can evaluate an exact completed-step clause, but the public model prompt omitted that rule and validation required compiler-internal integer fields and citation IDs. The new public percentage-string representation closes that proposal-flow gap without changing source grammar, credit arithmetic, governing-fee authority or review policy.

The authored Aster Cove Compute source and controls were frozen at `b2edd35` before implementation. The source SHA-256 is `ee180cf751326c965bda4b1a4dd2fa58389cdf7e1618c1750c83dc806c887bfa`. `fixtures/opus70_public/before.json` preserves the old rejection. This is an authored public test set, not a blind or previously unseen independent evaluation score.

## Actual implementation delegation

Claude Code 2.1.318 initialized **claude-opus-5-5**, session **3f05414d-7589-4757-b63c-04ee4d003c7a**, with requested effort `xhigh` and exactly `Read`, `Edit`, `Write`, `Glob`, `Grep`. It criticized the concrete preferred design before its first file operation, then implemented `uptime/vendor_model.py` and a new test module. It had no shell, test, git or network tool. The permitted working directory was this worktree's `uptime`; additional directories were only its `tests` and the new public fixture directory. The parent ran all tests and git operations.

The [packet](packets/70-public-completed-step-proposal-implementation.md) and [actual response/identity receipt](reviews/70-actual-opus-implementation.json) preserve the first criticism, final response, initialized tool inventory, invocation, file hashes and raw stream reference. This tool-enabled implementation session is not a tool-free extraction receipt. Its written note is explicitly labeled accordingly.

## Choice and criticism

The new value has exactly `kind`, `product`, `plan`, `target`, `step`, `credit`, `cap`; all are strings, and kind is `completed_steps`. Percentage strings use shortest plain ASCII decimal form with at most six fractional digits. Conversion uses existing `percent_units`. The compiler supplies the citation of the same independently compiled source span; every resulting field must equal the compiled rule. The existing normalized representation remains accepted with strict types. Legacy tier proposals retain their previous representation and acceptance.

The worker initially worried that the proposal lacked a span anchor, then confirmed the existing outer `quote` and ordered complete-source coverage already provide it. No second span resolver was introduced. Its preferred canonical decimal spelling narrows only the new wire form; no fuzzy numeric repair is attempted. `credit_rounding` must match the existing explicit source clause. Neither a declared rounding preference nor an omitted source sentence invents a default.

Rejected alternatives were requiring the model to supply compiler IDs/units, ignoring proposed values after source compilation, or creating a new family/grammar. They respectively retain the representation gap, discard a required consistency check, or change more semantics than necessary. Unknown/conditional/started-step prose and unsupported neighbouring clauses continue to refuse.

## Evidence and limits

The parent corrected only missing required Scope identifiers in the worker's new test helper after retaining the initial 127-pass/7-fail run. The subsequent focused suite passed **238 tests**. Tests exercise the normal candidate, shadow, review, activation, dispatch and rollback interfaces with explicitly scripted reviewer and billing fixtures. Positive credit requires current sealed governing-fee authority; missing, stale or mismatched context leaves amounts null. No test fixture establishes actual human approval or authenticated provider evidence. Exact changes are in [the ledger](../TEST-CHANGES-70.md).

The implementation changes a code dependency of semantic review. Old approvals are not relabeled current; existing review-required behavior applies. Frozen source bytes, offsets, source hashes, economic identities and archived receipts remain unchanged. Rollback is a code revert followed by the existing fresh review lifecycle; it does not rewrite historical artifacts or reactivate old approval silently.

This increment supports the already bounded completed-step grammar through the model proposal interface. It does not establish general free-prose understanding. Genuine public model extraction, when run, is recorded separately from this implementation delegation and from authored deterministic control scores.
