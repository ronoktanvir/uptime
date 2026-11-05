# Local reviewer authority

The default launcher starts an observation-only local workspace. Named accounts are provisioned by the operator from the CLI. The HTTP application offers sign-in and sign-out. Enrollment is an offline filesystem operation.

## Human use

Choose a fresh V4 database. Run these commands from the repository with its Python environment.

```sh
python scripts/serve.py --mode replay --db runtime/demo-v4.sqlite --enroll alice.smith \
  --credential-file /absolute/private/path/alice-uptime.json
python scripts/serve.py --mode replay --db runtime/demo-v4.sqlite --open
```

Enrollment generates a random P-256 key and creates the chosen private JWK file outside the repository with mode 0600. It refuses existing files. Select that file and enter the enrolled account name on the sign-in screen. An operator can instead pass `--public-key public.json` to register an existing public P-256 JWK. Add `--role viewer` to provision an observation-only account. Each person needs their own enrolled key. Consequential local actions require an explicit `--enable-local-approvals` launch and a valid release receipt verified by `uptime.gates.local_release_ready()`. Browser requests and environment variables cannot activate the gate.

The identity is a locally provisioned human account. The prototype relies on the operator's enrollment decision and local filesystem access. The database stores public verification keys. Only possession of the matching private key permits authentication. A database disclosure cannot generate reviewer signatures. The operator must protect the private credential file and prevent unauthorized changes to account enrollment. The launcher uses private filesystem permissions. Remote identity verification, production SSO, and hardware-backed proof are outside this prototype.

## Request authority

The app accepts only the configured exact loopback origin, including its port, from a loopback client. Every POST needs the matching Origin, JSON content type and action header. Cross-origin browser requests fail preflight and the server does not enable CORS.

A sign-in challenge contains a fresh nonce, runtime identifier, origin, execution mode, identity, expiry, method and endpoint. The browser imports the selected private JWK as a non-extractable ECDSA P-256 key and signs the challenge with SHA-256. Only the signature travels over HTTP. Proofs use the Web Crypto 64-byte r/s encoding. This revision adopts random reviewer keys following independent review 22, which identified offline password guessing and password-equivalent stored verifiers as weaknesses of the earlier proposal. A challenge is consumed even when a proof fails.

Sign-in yields a one-hour read token in per-origin, per-tab sessionStorage. Requests explicitly send it as a header. The app issues no authentication cookies and no credential-bearing URLs. The signing key remains in the page's memory as a non-extractable Web Crypto key. Reloading a page preserves read access and requires sign-in again before a write. Closing the tab loses its in-memory signing key. Browser session restoration may retain the read token until it expires or the server restarts. A local OS compromise or same-origin script compromise can impersonate the local account. Protect the local machine and serve only reviewed assets.

Each consequential POST requires another single-use challenge bound to its exact raw body digest, encoded path, read session and current action revision. It expires after 60 seconds. An authenticated write or inbound service delivery invalidates earlier pending write challenges. HTTP mutations are serialized in one process. Domain workflows must also validate their own durable resource revisions, since those revisions cover changes outside this HTTP runtime.

Sessions and challenges are held only in the current process. Restarting invalidates both, even with the same enrolled key. The database records its mode and human/rehearsal namespace. Opening it in another namespace or mode fails. An unscoped V3 database or a workspace containing the earlier password-authority schema requires a fresh V4 workspace and offline key enrollment. The original V3 workspace remains the rollback artifact.

## Scripted rehearsal and service identities

The capture and rehearsal scripts create a temporary replay database and derive a P-256 key from a random, process-local rehearsal secret. This compatibility path is limited to the reserved scripted identity and explicit rehearsal namespace. Human enrollment rejects string passwords and marked rehearsal keys. Their account is `scripted-test-reviewer`. The same UI or native challenge protocol authenticates that identity. Normal account enrollment forbids this reserved identity, and normal mode cannot open a rehearsal database. The disposable script identity demonstrates simulated review.

The launcher provisions per-source Ed25519 public verifiers through an offline config. Service requests are signed by a private file retained by the source. The server binds the signature to tenant, runtime, origin, execution mode, subject, path, body, timestamp and nonce, checks the source's full scope, and records key and grant fingerprints on the authenticated principal. HMAC is available to explicitly named synthetic fixture subjects or a scripted rehearsal embedding. See [Local synthetic evidence intake](../v4/SOURCE-INTAKE.md).

## Integration and verification

`create_app` accepts trusted embedding/test configuration for `approvals_enabled`, `origin`, `service_credentials`, and the explicit rehearsal options. The launcher verifies release evidence before enabling the gate. A route integration can implement `uptime.v4_routes.register_v4_routes(app, bench, auth)`, with `Depends(auth.actor)` for reads, `Depends(auth.reviewer)` for signed human writes, and `Depends(auth.service)` for signed service deliveries.

`uptime.auth_keys.generate_reviewer_key()` creates a random private JWK for a disposable native test. Pass it to both offline `enroll(...)` and `uptime.auth_client.ReviewerClient(...)`. `service_headers` signs delivery proofs using the configured Ed25519 source credential or an explicitly synthetic HMAC fixture. The browser exposes `window.uptimeAPI(path, payload)` for authenticated reads and signed writes. `tests/test_v4_authority_browser.py` launches real Chromium against two owned localhost ports, captures every request arriving at the sibling, attempts browser cross-origin access and native replay, and verifies a named positive-control approval. All traffic stays on the owned loopback listeners.
