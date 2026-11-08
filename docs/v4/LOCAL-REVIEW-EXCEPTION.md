# CalyxQuay local permission review

**Prepared and tested; not enabled.** The exact unsigned proposal is `/Users/ronoktanvir/.local/share/uptime-engineering/runtime/ronok-review-87/review-proposal-88.json`. Ronok's workspace remains SHADOW at revision 5, with no named approval or active adapter. No operator approval, reviewer signature or installed exception exists. The only existing lifecycle actors are the explicitly scripted preparation records.

| Review item | Exact scope |
|---|---|
| Reviewer | Ronok Tanvir, account `ronok-tanvir` |
| Workspace | `/Users/ronoktanvir/.local/share/uptime-engineering/runtime/ronok-review-87` at `http://127.0.0.1:8777` |
| Adapter | CalyxQuay version `5616fe29c195e9689a22fae149dac2326f36c570b2759e7f90587d491d174725` |
| Permitted controls | Interpret the source, approve, activate and perform terminal rollback of this version only |
| Validity | November 7, 2026 at 6:15:02 PM Pacific through November 9, 2026 at 6:15:02 PM Pacific. The window starts when prepared; signing later does not extend it. |
| Excluded authority | Claims, dispute submissions, awards, credits, bill/payment actions, policy/source changes, model jobs and every Ramp mutation |
| Tested application | `6bedefc4550dc5bee3187645f4ead9068b1ebbc3`; 3,967 passed, 1 warning in 232.13 seconds |
| Proposal SHA-256 | `71de8eddfe7e39b7f11191a7315a3c79e66ca3e07105e2398974e42ad1d48556` |
| Grant ID | `8c053c1f1a1de5dfbb003a6144aad9cf` |

[Exact full-suite evidence](evidence/local-review-88/verification.json) · [Read-only preparation check](evidence/local-review-88/preparation.json) · [Test changes](TEST-CHANGES-88.md) · [Decision and Opus disagreement](decisions/ADR-0088-local-review-exception.md).

## What approval means

This grants temporary permission for Ronok to demonstrate ordinary adapter review controls in this local authored workspace. It is not a real customer's contract approval, an independent release certification, or permission to act in Ramp. The standard release gate remains the default for every other launch.

Two explicit steps are required after reviewing this exact proposal: the operator approves its exact hash into the fixed protected host authority store; Ronok signs the same proposal with his enrolled key. The launcher must then be explicitly pointed at that signed envelope. The same person may hold both roles, so this is not represented as independent separation between people. Merely possessing the unsigned proposal, reviewer key or a signature does not enable the exception.

The host authority retains revocation and terminal rollback outside the workspace. Expiry, revocation or changed code/source/version freezes permission. Historical ACTIVE state can remain visible after expiry; evaluation and further mutations are refused. Complete rollback before expiry. A new grant requires a new proposal and exact operator approval. The host administrator remains trusted; replacing the entire authority store is outside this protection.

## Inspect before deciding

Run from the repository:

```sh
uv run --locked python scripts/review_local_exception.py inspect \
  --proposal "$HOME/.local/share/uptime-engineering/runtime/ronok-review-87/review-proposal-88.json"
```

Verify the hash, version and expiry against the table. Do not edit the proposal or the verification receipt: both are pinned. Changed code or evidence needs a newly tested and staged proposal. This preparation did not read Ronok's private credential.

## Only after explicit approval

These commands are a person-operated handoff. **They have not been executed.** The first records operator permission; the second signs it. Neither substitutes for Ronok's later browser review clicks.

```sh
uv run --locked python scripts/review_local_exception.py owner-approve \
  --directory "$HOME/.local/share/uptime-engineering/runtime/ronok-review-87" \
  --proposal "$HOME/.local/share/uptime-engineering/runtime/ronok-review-87/review-proposal-88.json" \
  --reviewed-sha256 71de8eddfe7e39b7f11191a7315a3c79e66ca3e07105e2398974e42ad1d48556

uv run --locked python scripts/review_local_exception.py authorize \
  --directory "$HOME/.local/share/uptime-engineering/runtime/ronok-review-87" \
  --proposal "$HOME/.local/share/uptime-engineering/runtime/ronok-review-87/review-proposal-88.json" \
  --credential-file "$HOME/.local/share/uptime-engineering/runtime/ronok-review-87/reviewer.jwk" \
  --reviewed-sha256 71de8eddfe7e39b7f11191a7315a3c79e66ca3e07105e2398974e42ad1d48556 \
  --output "$HOME/.local/share/uptime-engineering/runtime/ronok-review-87/review-envelope-88.json"
```

Stop only the existing dedicated 8777 listener, preserving its directory. Then start the explicitly authorized listener:

```sh
uv run --locked python scripts/setup_live_reviewer.py \
  --directory "$HOME/.local/share/uptime-engineering/runtime/ronok-review-87" \
  --resume --serve \
  --review-exception "$HOME/.local/share/uptime-engineering/runtime/ronok-review-87/review-envelope-88.json"
```

Ronok signs in at http://127.0.0.1:8777/#vendors, inspects the exact source/overlay/shadow checks, accepts the interpretation, approves, activates, inspects his audit entry and rolls back. The last step ends this grant permanently. Do not automate those clicks or describe the earlier scripted history as Ronok's decisions.

For early withdrawal:

```sh
uv run --locked python scripts/review_local_exception.py revoke \
  --grant-id 8c053c1f1a1de5dfbb003a6144aad9cf
```

Revocation prevents further actions; it does not erase history or perform an automatic rollback. The agent-run native-posting refusal remains unchanged. The already-posted human Ramp note and its API confirmation are separate evidence.
