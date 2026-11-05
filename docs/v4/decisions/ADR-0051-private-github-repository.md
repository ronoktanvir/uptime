# ADR 0051 — Private GitHub engineering repository

## Decision

Publish the integrated application as a private `ronoktanvir/uptime` repository. Preserve source history and cited commit identifiers. Push the integration branch explicitly to `main`, then continue with bounded workstream commits and tested merges. The user's request authorizes this repository creation and code publication.

## Alternatives and cost

A fresh squashed root would simplify the visible log but invalidate source-pinned audit references. Pushing every experimental branch would expose unnecessary work and could include private evaluations. Keeping the code local would leave the new request incomplete. Reachable-history inspection and a fresh remote clone are required costs of publication. The original alternatives and falsifiers are retained in [the packet](packets/51-private-github-repository.md).

## Independent review and final rationale

The actual `claude-opus-5-5` review is session `ed3b57cc-7d61-4943-b2e2-0b63117b2682`, packet SHA-256 `a2af29eb5d71d1213726c1810f92ae68d4520073dc48f1066e9c863bac323bc2`. Its [receipt](reviews/51-private-github-repository.json) includes the complete response.

Accept the reviewer's reachability objection. Main-only selection requires inspection of all reachable objects because a merge also publishes its parent history. The publication check includes commit metadata, raw and encoded known credentials, common token/key patterns, nested ZIP contents, runtime filenames and SQLite headers. The only reachable gold files found by path review are the original committed synthetic onboarding fixtures. Private independent corpora remain outside the published history.

Accept the correction that repository deletion cannot guarantee erasure of third-party caches. Privacy is a publication decision made before pushing. The exact existing code history remains valuable because its audit findings and later corrections can be inspected independently. No history rewrite, collaborator addition or visibility change is part of this decision.

## Verification and rollback

Before publication, the existing secret check passed996 versioned text objects. A separate reachable-history report records the complete metadata/blob checks. The repository must remain private, remote `main` must match the selected local commit, and a fresh clone must contain exactly the intended reachable object set. GitHub CI will report its actual status.

If a pre-push scan finds sensitive history, stop publication and quarantine the finding without displaying secret bytes. Any proposed rewrite requires an explicit old-to-new commit mapping and user agreement because existing receipts depend on those identifiers. After publication, stop further pushes if needed and coordinate any remote visibility, deletion or credential-revocation action with the user. Preserve the local source and audit history.

