# ADR 88 — prepare an exact local adapter permission exception

Status: implementation authorized for review; actual owner approval, signing and activation are pending. November 7, 2026, America/Los_Angeles.

The user selected “Prepare the limited exception for review.” This permits construction and testing of a 48-hour local capability, not activation of that capability or a claim that independent release evaluation passed. The original release gate stays the default; the dedicated reviewer launcher gains an explicit, narrower alternative. That changes its authorization semantics and is not described as merely documentation.

[Decision packet](packets/88-local-review-exception.md) · [Actual Opus 5.5 critique](reviews/88-local-review-exception.json), session `d88cb8c3-92b1-479d-b2a2-84a3aee2f173`.

## Choice and scope

Prepare an unsigned proposal pinned to the physical workspace and database realm, local origin, fixture tenant, enrolled reviewer/public key, CalyxQuay source/version/shadow evidence, exact tested application source and a maximum 48-hour window. The dedicated installation has no native configuration, external source grant or model provider. No financial mutation is in scope.

Before that proposal can enable anything, two explicit offline actions are required: an operator-owned approval of its exact hash, retained under a fixed protected authority directory outside the workspace; and the reviewer's domain-separated signature over the canonical proposal. Neither action is performed during preparation. The HTTP API cannot create either authority item or select another authority directory.

The exception listener accepts only the normal signed CalyxQuay interpretation, approval, activation and rollback controls for that precise version and actor. Ordinary signatures, current action IDs and state transitions still apply. All other mutation routes remain refused, including claims, disputes, credits, policy, source changes, model jobs and Ramp actions. Expiry or invalid authority freezes the capability and refuses evaluation; it does not rewrite historical activation records. Rollback is terminal for that grant. A new proposal requires a new exact owner approval.

## Criticism and disagreements

Opus identified a valid flaw in the initial one-signature sketch: reviewer self-signing did not enforce a separate policy-owner action. The selected implementation adds the fixed operator approval store and requires both channels. It also adopts domain separation, exact raw and routed paths, current/loaded source binding, time limits, separate durable revocation and rollback finality.

Opus recommended two distinct signing keys. For this single-owner local fixture workspace, the selected boundary uses protected offline operator installation plus a reviewer signature. A named reviewer using only the browser cannot issue or install the operator approval. The same person may control both channels; this is explicitly not independent review, commercial signing authority or a substitute for the full release. A deployment requiring separation between people would need separately trusted owner keys and custody controls.

The application retains audit history without update/delete operations; the local filesystem administrator remains trusted. Revocation outside the workspace survives restoration of a workspace snapshot. It is not claimed to survive malicious restoration or replacement of the entire host authority store. Physical-path and host-binding checks reject ordinary copied workspaces, not an administrator cloning all trusted local state.

## Validation and rollback

The workstream tests exact signed lifecycle behavior with disposable keys, refusal without operator approval, malformed/expired/revoked/stale grants, wrong workspace/origin/key/source/version, forbidden routes and representations, rollback finality and source changes. Separate dispute controls verify that a valid local-review capability still cannot file, respond, award, post or apply funds. Root runs the locked complete suite after integration and stages the unsigned proposal only against that tested code.

To remove the exception, revoke its authority in the protected host store and stop its listener, then use the existing release-gated launcher. Preserve all prior audit events. Never retry native posting through this path. Concrete source, version, expiry, tests and operator commands belong in the final prepared review record.
