# Authored workspace setup and execution

The configured generic workflow runs on a fresh isolated replay/rehearsal database. The actual reviewer is `scripted-test-reviewer`; Dana Reyes is a fictional display alias. The destination is Local ledger. No real customer workspace, Ramp credit or actual-human promotion is created.

Create and serve a fresh directory outside the repository:

```sh
uv run --locked python scripts/setup_northwind.py --directory /absolute/owned/workspace --origin http://127.0.0.1:8786 --serve
```

The setup completes signed source intake and the reviewed catalog lifecycle before serving. Sign in with account `scripted-test-reviewer` and the generated `scripted-reviewer.jwk` file in that directory. The file is0600 and contains the existing scripted credential; keep it private. `workspace.json` is also private and is not the browser credential. No credential bytes are printed. To restart the same source-stable workspace, add `--resume`. Changed package/source authority requires a new workspace and review; old receipts remain preserved.

GET `/api/workspace/workflow` returns the ordinary projection or `{workflow:null}` when unconfigured. Each offered opaque action is submitted to `/api/workspace/workflow/actions/{id}` with an exact empty signed body. Callers cannot choose amounts, time, source identity or destination. The ordinary `#ramp` view consumes this envelope.

For socket verification against the running owned listener:

```sh
uv run --locked python scripts/rehearse_northwind.py --directory /absolute/owned/workspace --receipt /absolute/owned/socket-receipt.json
```

The client verifies the configured database instance, package and replay authority, performs offered actions, repeats each action with a fresh proof, and independently reads its resulting state. It never derives an award from an expected answer. The fixed vendor messages and supplementary log are authored inputs; their runtime signatures exercise the existing verifier and are not independent external attestation.

The completed sequence is January2400 claim, missing-log response, separately signed artifact and verification, approved response after cooldown, award, local posting, then April1 invoice intake and application. April11000 becomes8600; March's1000 price exposure remains unresolved. January/February/March remain the only SLA assessment months. Quoted governing clauses, source hashes, actual scripted actor and separate pricing/award versions remain inspectable in the API records. Financial stages are not summed.


## Separate teammate review

Do not enroll Ronok into the scripted Northwind database or relabel its old audit entries. Prepare a fresh normal replay installation for the teammate:

```sh
uv run --locked python scripts/setup_live_reviewer.py \
  --directory "$HOME/.local/share/uptime/ronok-review-001" \
  --subject ronok-tanvir \
  --credential-file "$HOME/.local/share/uptime/ronok-review-001/reviewer.jwk" \
  --origin http://127.0.0.1:8777 --serve
```

Prefer `--public-key /absolute/protected/ronok-public.jwk` when Ronok supplies a public key whose private half he controls. The alternative above creates a team-provisioned private key outside Git; its signature demonstrates key possession, not exclusive personal custody or legal authority. Ronok chooses the private file in the normal sign-in form. Setup never signs in or acts as Ronok.

The setup imports source/overlay/bindings and three shadow controls with scripted attribution. It leaves CalyxQuay in SHADOW with no interpretation, approval, activation or rollback by Ronok. The normal release verifier remains mandatory at startup and each consequential request. Without current independently signed gate evidence and human witness, the helper reports RELEASE_PENDING and promotion remains disabled. After valid release evidence is installed, restart with `--directory ... --resume --serve`; then Ronok inspects sources, accepts the exact interpretation, approves, activates, inspects audit/version and rolls back. Do not use test monkeypatches or flags to enable the demonstration.

The separate listeners are advanced Uptime review tools. They do not embed pages into Ramp or transfer Northwind data into a Ramp bill. [Current proof and remaining gates](DEMO-PATH-87.md).
