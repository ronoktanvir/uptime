# ADR 91a — Twilio's public status page as the first real evidence source

Status: implemented on `work/evidence-custody-90` (`6d3536f` source, `9eafdf5` rehearsal); **intake verified with a live public capture; release gate pending.** November 9, 2026. Workstream W5. Implements the evidence-source element of D07 (narrow published matrix, decided November 9 by Ronok; relayed from his overview session and recorded by the integration owner).

[Decision packet](packets/91a-public-status-source.md) · [Actual Opus 5.5 critique](reviews/91a-public-status-source.json), session `6e0ce0dd-8e29-41c8-9da3-c2dec50de3b2` · [Live receipt](../evidence/evidence-custody-90/public-status-live-91a.json) · [Support matrix, section 7](../EVIDENCE-SUPPORT-MATRIX-91.md)

## Choice

D07 requires one real evidence source onboarded end to end and does not name it. The only real sources available are Twilio's official public status feed (public, credential-free), Ramp sandbox bills (another workstream's credentials; no governing agreement or line terms) and customer telemetry (none exists). The status feed is chosen, for the `status` role only, because it needs no credential, discloses no customer data, performs no write and runs locally under D11. It was also chosen partly because it was available; the critique says so plainly, and that is recorded here.

`uptime/evidence_status_source.py` maps one verified, integrity-checked snapshot and one operator-selected incident to one signed `status` record for an exact enrolled grant. `scripts/deliver_public_status.py` runs the existing signed delivery client. The checks, provenance and limits are listed in matrix section 7. The record never states customer impact, fees or month coverage, and the connector never emits a coverage record.

## Live evidence

On November 9 at 12:26:26 UTC one unauthenticated HTTPS GET fetched the official feed: 50 incidents, raw SHA-256 `7e974ffd…583a`. The minimized snapshot is retained beside the receipt. A fresh loopback workspace was started with the test-suite app factory and disposable keys, a status source was enrolled with the ordinary provisioning functions, and the actual CLI delivered resolved incident `fm5fk85h6glc` (October, component `50pr269zqrwj`) as event `twilio-status:fm5fk85h6glc:a446ee1798d6acb6`. A second CLI run returned the identical receipt. The claim stayed `INSUFFICIENT_EVIDENCE` with no amount, waiting for a customer impact record. An earlier dry run with the recorded November 4 capture was refused before signing as older than 24 hours, and nothing was stored.

## Criticism and disagreement

Opus judged this defensible as proof that real external bytes reach intake, not as complete "end to end", and said it must not be reported as "D07 satisfied". **Accepted:** the status is "intake path verified, launch path unverified". The ordinary launcher accepts deliveries only after the release gate verifies; that gate is unsatisfied and was not touched. Whether a harness-hosted rehearsal counts toward D07 is the decision owner's call.

Accepted and tested: identity across two separate fetches with reordered serialization; a public edit producing a contradiction for review; component matching by stable ID; explicit UTC month rule; truncated history refusing as "not in this snapshot"; trusted clocks stated. The existing test `test_signed_delivery_native_receipt_and_forgery_rejection` already shows that the closed default launch refuses the same credential.

Opus asked to block live claim use until W4's F3 change lands. **Agreed:** with no coverage record, the current Twilio profile would treat this one status record as complete month coverage. This connector is intake evidence only until F3 lands.

Opus asked to prevent replay of one snapshot against multiple grants. **Disagreed:** one public incident can legitimately be relevant to several customers' claims, each through its own operator-enrolled grant naming that incident and component. Each delivery is separately signed and scoped; nothing is shared across grants.

## Validation and rollback

15 new tests in `tests/test_evidence_status_source_91a.py`, using the recorded official capture. W5 evidence suites: 75 passed, 1 warning in 5.01s. No existing module behavior or test changed; the new module is not imported by existing code. Full-suite verification belongs to the integration owner's post-merge run.

Rollback: delete the module, the two scripts and the test file; stop using the enrolled status grant (`provision_sources.py revoke`). Already-stored deliveries remain as history.
