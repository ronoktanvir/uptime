# Source and literal evidence review

A free-form source label is an identifier, not an observed fact. A named reviewer must resolve source meaning before affected pricing. This review is separate from independent tests, formula interpretation, final approval and activation; none of those stages implicitly supplies it.

Read `GET /api/vendors/{installation}`. `semantic_review_requirements` contains the full original source and URI, source/manifest/overlay/dependency hashes, every source block with its supported effects, and every role-specific definition with all exact possible source occurrences. Original offsets and block hashes are retained. A missing occurrence is unresolved; do not substitute a nearby phrase. Multiple occurrences require an explicit selection after reading the full source, conditions and overrides.

Submit with the existing full reviewer authentication and exact signed write proof:

```
POST /api/vendors/{installation}/semantic-bindings
{
  "revision": <current revision>,
  "review": {
    "source_sha256": <returned pin>,
    "manifest_sha256": <returned pin>,
    "overlay_sha256": <returned pin>,
    "dependency_sha256": <returned pin>,
    "attestations": {
      "complete_source_reviewed": true,
      "conditions_supported": true,
      "overrides_resolved": true,
      "evidence_meaning_verified": true,
      "scope_verified": true
    },
    "block_reviews": [
      {"block": <id>, "block_sha256": <pin>, "effects": <exact returned list>,
       "conditions_and_overrides": <reviewer's resolution for this block>}
    ],
    "bindings": [
      {"definition_id": <id>, "span_id": <selected exact occurrence id>,
       "literals": [<explicit permitted raw evidence representations>]}
    ]
  }
}
```

Every block and definition is required. Attestations must be JSON `true`; no defaults or coercion supply consent. Literal matching preserves case, punctuation, underscores and Unicode distinctions. Only the established space/tab/LF/CR/NBSP equivalence applies. No literal is automatically obtained from an opaque ID or a private overlay alias. The complete overlay is separately pinned, so changing account, resource, region, edition or private scope invalidates the review.

Roles cover qualifying symptoms, provider causes, exclusions, fee exclusions, filing fields, maintenance causes and separately attributed telemetry. Where fee exclusions exist, `fee_inclusions` binds positive charge-category representations to the already-supported fee-basis clause. A category outside both reviewed sets is unknown. A role match cannot supply evidence under a different role. A raw string still remains a raw string: this interface does not add typed definition references to signed source events.

Successful review creates a new candidate version and clears prior test results and approvals. Submit independent scenarios, then use the offered interpretation, approval and activation actions. `POST /api/vendors/{installation}/semantic-bindings/revoke` with `{"revision": <current revision>}` immediately removes current capability; it retains immutable review, source, event and receipt history. Re-review changes the approval version, while the economic obligation and existing dispatch reservation remain stable.

For isolated synthetic rehearsals, `scripts.rehearse_vendor.exercise(..., semantic_review=payload)` and CLI `--semantic-review path.json` accept a separately authored review. They never generate it from scenario answers. The authority remains `scripted_test`, not an actual human decision. The test helper `tests/test_vendor_semantic_bindings.py::review_submission` is explicitly a synthetic unit fixture and is not a production approval utility. Draft-only credentials cannot call the review endpoint and therefore receive no affected monetary preview.

Deployment must stop old processes before opening an upgraded database. The additive epoch refuses the tested older startup but cannot stop a process already running old code. See [ADR 61](decisions/ADR-0061-source-semantic-bindings.md) for the actual old-build receipt and limits. Historical estimates remain recorded history; absent current authority makes current financial projections unavailable without rewriting those artifacts.
