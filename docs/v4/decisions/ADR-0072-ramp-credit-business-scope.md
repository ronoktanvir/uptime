# Decision 72: preserve business identity in read-only credit reconciliation

Status: implemented and focused checks passed; integration owner runs the required post-merge suite.

## Reproduced defect and decision

The native workspace pins its tenant to a Ramp business, but its credit projection discarded that business. The offline credit journal likewise discarded caller-supplied business identity. In an authored pre-fix reproduction, a credit linked under business A with 200 applied minor units advanced to 500 after importing the same native credit and bill IDs under business B. The import returned `RECORDED`. This was a local correctness defect, not an actual Ramp credit or recovery observation.

Preserve an explicit business ID through the workspace projection, journal, binding and summary. Credit sync pins one business per tenant because the existing allocation ledger keys financial objects by tenant and native ID. A foreign business is rejected before storage or financial changes. This is an operator custody assertion; it does not authenticate OAuth identity or establish an award.

The financial amount distinction also needs correction: an absence of linked native credit evidence yields `recorded_cents=null` and `applied_cents=null`. A linked credit with an explicitly observed zero bill application still yields zero applied. No amount becomes earned or recovered merely because a capture exists. `actual_recovery` remains null.

## Alternatives and accepted criticism

The initial proposal grouped history by business. Actual Claude Opus 5.5 criticism identified that grouping alone cannot isolate ledger rows: allocation credits, bills and applications still share tenant/native-ID keys. Its recommendation to enforce a single immutable business pin per tenant was accepted. Changing every allocation key and introducing multi-business tenants is unnecessary for this repair.

Automatically copying a newly supplied business into historical snapshots or bindings was rejected: old observations lack that evidence and their immutable digests must remain stable. Treating every missing historical scope as a monetary conflict was also rejected. The journal's quarantine has no clearance workflow, and missing evidence does not establish a contradiction.

Legacy unmarked unscoped financial observations and bindings remain historical, block new attribution or application advancement, and report `LEGACY_UNSCOPED_HISTORY`. New observation-only rows carry `BUSINESS_SCOPE_MISSING` and never projected money, so they do not freeze later correctly scoped observations. This distinction avoids unnecessary lockout without retroactively assigning a business. Legacy empty observations do not establish financial identity and do not prevent a later independently supplied business pin. Unscoped new observations are observational only and report `BUSINESS_SCOPE_MISSING`. Existing quarantine, strict money, reciprocal bill checks, independently recorded award, eligible bill capacity, draft separation and tenant checks remain in force.

## Actual model contribution and access boundary

[Public model receipt and actual final criticism](reviews/72-ramp-credit-business-scope.json) provide the exact model/session/tool inventory and protected-stream hashes without publishing full process transcripts.

The lead requested one concise critique, then delegated the bounded implementation to actual Claude Code with model `claude-opus-5-5`, high effort. The critique session was `49c03fb7-9bd3-45b2-a6c0-424d6d6b6d62`; its verified init exposed only `Edit`, `Glob`, `Grep`, `Read`, and `Write`. The process used safe/restricted mode, no shell or network tool, no MCP server, no Chrome, and no session persistence. Its working directory was `uptime`; only the authored tests directory was added. It read source code and authored local test inputs. The implementation trace also records a Glob of repository-root configuration filenames; the repository root was not added as a permitted directory and no configuration contents were read. No customer capture, credential file or private evaluation material was provided.

Protected response references are outside Git under `/Users/ronoktanvir/.local/share/uptime-engineering/review/decision72/`: `critique.jsonl`, `implementation.jsonl`, and `baseline-reproduction.json`. The implementation session was `71662529-d690-45c5-b6fb-bcc3819f9a69`, also verified as `claude-opus-5-5` with the same five tools. It made 27 Edit/Write calls and completed successfully. The lead inspected the patch, added business identity to immediate import receipts (rejecting omission merely to avoid one test change), rejected a zero business before workspace persistence, and added two local integration checks. The first invocation used a mistaken executable filename and failed with FileNotFoundError before any model process started; the corrected executable was `/Users/ronoktanvir/.local/bin/claude`. No failed invocation is represented as a consultation.

## Validation and rollback

Pre-change focused baseline: 102 tests passed in 2.60 seconds for credit sync and allocation ledger. The authored reproduction retained the accepted foreign-business result and the unobserved-tenant numeric zero. The delegated patch first passed 132 tests in 3.69 seconds. After the lead's bounded corrections, the final sync/ledger suite passed **134 tests in 3.15 seconds**; adjacent workspace and signed-award-attribution suites passed **120 tests with 1 existing Starlette deprecation warning in 9.07 seconds**. `git diff --check` passed. No full-suite or live-provider result is claimed here.

Exact verification commands:

```sh
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python -m pytest tests/test_ramp_credit_scope_v72.py tests/test_ramp_credit_sync_v4.py tests/test_allocation_ledger.py -q --basetemp=/tmp/ramp72-final
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python -m pytest tests/test_ramp_workspace_installation.py tests/test_ramp_award_attribution.py tests/test_ramp_award_claim_integration.py tests/test_ramp_award_procedural.py -q --basetemp=/tmp/ramp72-adjacent
```

Protected response SHA-256: critique `87e96a982190eaddbfa2897b5d6dba333b511eab62f35754594e5582fb3fb50b`; implementation `689f9dcf1d6000498abf7933ae93bef7554dad968d47b8b24a5bf08460bc40cf`.

[Exact test changes](../TEST-CHANGES-72.md) document the changed assertions and fixture scope. This increment creates no provider transport, write operation, credit, award or bill. Actual captured credit inventories may remain empty. The blocked native qualification work is excluded.

Rollback is a code revert while preserving the immutable journal and its new scope table. Do not delete history or drop scope protection on a database that has admitted scoped financial records; restoring the old writer against that database would restore the demonstrated vulnerability. Deployment downgrade therefore requires retaining read-only operation or a separately reviewed migration.
