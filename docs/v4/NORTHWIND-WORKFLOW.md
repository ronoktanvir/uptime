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
