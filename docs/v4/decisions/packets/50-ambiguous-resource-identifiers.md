# Proposed bounded correction for ambiguous resource identities

The current v2 key can merge separate financial obligations because its resource remedy concatenates identifiers containing the delimiter. Preserve existing unambiguous keys and refuse new financial use of ambiguous resource identifiers until an independently verified, append-only alias migration exists.

## Reproduced mechanism

`claim_identity.resource_remedy` emits `resource-month/` plus resource and, for a regional subscription, `/` plus region. Both the source overlay and correspondence Scope permit `/` inside identifiers. Two independently covered tuples such as resource `cell/a`, region `North` and resource `cell`, region `a/North` both produce `resource-month/cell/a/North`. The same ambiguity exists between ordinary resource `cell/North` and regional resource `cell`, region `North`. Ordinary resource `aggregate-service` also collides with the existing whole-service aggregate sentinel.

The portfolio grouping key and v2 dispatch key both consume this remedy. The prior collision can collapse historical estimates or prevent a legitimate separate dispatch. Simply escaping delimiters or replacing the remedy with a tuple hash changes the key of existing financial claims. An old writer or unconverted reservation can then permit duplicate ownership under the new key.

## Recommended reversible change

1. Keep the exact existing strings for monthly whole-service, aggregate whole-service and unambiguous resource/regional scopes.
2. Make the common resource remedy constructor refuse `/` in any resource identifier or economically relevant region. Refuse the ordinary resource identifier `aggregate-service`, which is already reserved for the aggregate profile. Apply the same constructor during reviewed overlay binding, so normal new intake is quarantined before financial eligibility or publication.
3. Preserve every historical receipt, claim ID, archived source artifact, financial event and reservation byte. Create no v3 registry and no automatic old/new alias row. Version and source-document pins remain excluded from the deduplication key.
4. Existing evaluation semantics already bind the actual source files including claim_identity.py. A code change requires fresh interpretation of an old active adapter before subsequent monetary evaluation. An old ambiguous artifact fails fresh binding. The exact archived-artifact reader also refuses unresolved historical grouping rather than continuing to produce a merged portfolio total. This can withhold the affected portfolio response until manual reconciliation. Individual raw receipts and archived records remain retained.

## Compatibility and tradeoff

Unambiguous source identifiers retain their old remedy strings and canonical hash. Repeat dispatch and supplements continue to use the same immutable initial reservation. Existing source IDs containing delimiters need a future reviewed scope-registration/migration mechanism before renewed financial operations. Conservative refusal is the bounded tradeoff. Renaming identifiers in customer evidence would invent provenance and is excluded.

A future representation should explicitly encode measurement unit, resource and optional region, with an append-only verified alias map linking each old reservation and full original scope to its new identity. That migration needs tests for old readers, conflicting old aliases, restart, concurrent writers, local/historical originals, supplements, evaluation projection and native attribution. It exceeds this correction's scope.

## Required regression evidence

A test on the frozen implementation should demonstrate the equal output for the two distinct tuples, then expect controlled refusal for each ambiguous tuple after the patch. Controls should establish exact unchanged strings and hashes for existing safe resource, region and aggregate cases, quarantine through normal candidate intake, and byte-for-byte stability of a preexisting safe reservation after retry. Existing correspondence, source-pin, regional cardinality, portfolio and native tests remain applicable.

All examples are synthetic. No private evaluator corpus, gold, vendor source or commercial evidence is involved. Git metadata currently stalls, so the reversible source patch, tests and verification receipts will also be archived outside Documents.
