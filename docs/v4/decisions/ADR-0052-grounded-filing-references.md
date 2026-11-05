# ADR 0052 — Ground filing fields in signed source records

## Decision

Use exact signed source identifiers to express service and fee evidence within the existing aggregate correspondence schema. A specifically named fee requires one actual eligible row. A parent invoice identifier can reference that fee only after the required row is established. Preserve immutable original filing fields and source/version commitments.

## Alternatives and cost

Widening identifier syntax would permit display names without fixing missing fee evidence. Accepting every invoice for every field would manufacture support for absent rows. Keeping literal service names leaves names with spaces impossible to represent. Source-grounded references repair the supported protocol with a bounded lexical comparison and explicit ambiguity refusal. The correction affects one resolver and requires mounted-route negative controls and a separate independent cohort replay.

## Independent review and disagreement

The actual `claude-opus-5-5` review is session `90496b91-f9cf-4c13-8fbc-120ea5dfc19e`, packet SHA-256 `a8797f30b6ca5c6383fea5a36a851e5b8d85610e19ffdb8b55a4a3b6a66e4335`. The [packet](packets/52-grounded-filing-references.md), [response](reviews/52-grounded-filing-references.json) and [implementation disposition](../OPUS52-FILING-REFERENCE-DISPOSITION.md) preserve the complete reasoning.

Accept the contract-authority, category-provenance, negative-row and ambiguity objections. Field labels originate in the source-bound manifest, while categories and amounts originate in the independently signed invoice. The filer supplies references. Negative amounts and unsupported flags fail the strict schema. Credit-like kinds, absent rows and multiple matches withhold the reference.

The suggested per-line service identifier would introduce a new protocol representation. The current signed aggregate envelope already binds one exact service, agreement, account and month, and rejects unsupported multiservice fields. Retain that representation with exact signed source matching. A signature establishes issuer provenance, while evidence truth remains a separate concern. The user's authorized correctness remediation covers this reversible implementation. Actual vendor or financial dispatch still requires its separate authority.

## Verification and falsifiers

Root ran all33 focused filing-reference tests successfully after integration. Tests include independently signed intake, ordinary and historical denials, absent and unrelated fee rows, reinstallation, credits, reversed kinds, injected filing names and wrong issuer/scope. Existing evidence bytes and original source commitments remain preserved.

The independently frozen additive cohort originally achieved8/8 arithmetic results,0/7 denial dispositions and1/8 complete cases. That observed failure remains in the record. A fresh socket replay is required to measure the correction. A studied cohort's improvement establishes remediation under those cases. Further independent cohorts are required for broader generalization claims.

## Rollback

Revert the resolver correction and retain the evidence ledger and original receipts. Suspend affected submissions if a source reference admits an absent or ambiguous fee. Preserve failed attempts and re-run the same independently frozen inputs after any correction.
