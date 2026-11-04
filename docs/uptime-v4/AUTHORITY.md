# Local reviewer authority

The default launcher starts an observation-only local workspace. Named accounts are provisioned by the operator from the CLI. The HTTP application offers sign-in and sign-out. Enrollment is an offline filesystem operation.

## Human use

Choose a fresh V4 database. Run these commands from the repository with its Python environment.

```sh
python scripts/serve.py --mode replay --db runtime/demo-v4.sqlite --enroll alice.smith
python scripts/serve.py --mode replay --db runtime/demo-v4.sqlite --open
```

Enrollment prompts for a password of at least 14 characters without echoing it. Add `--role viewer` to provision an observation-only account. Each person should have their own named account and password. Consequential local actions require an explicit `--enable-local-approvals` launch and a valid release receipt verified by `uptime.gates.local_release_ready()`. Browser requests and environment variables cannot activate the gate.

The identity is a locally provisioned human account. The prototype relies on the operator's enrollment decision and local filesystem access. Its salted PBKDF2-HMAC-SHA256 verifier database must be protected as a secret. The launcher uses private filesystem permissions. Remote identity verification, production SSO, and hardware-backed proof are outside this prototype.

## Request authority

The app accepts only the configured exact loopback origin, including its port, from a loopback client. Every POST needs the matching Origin, JSON content type and action header. Cross-origin browser requests fail preflight and the server does not enable CORS.

A sign-in challenge contains a fresh nonce, runtime identifier, origin, execution mode, identity, expiry, method and endpoint. The browser derives an HMAC key with PBKDF2-SHA256, 600,000 iterations and a random per-account salt. Only the HMAC proof travels over HTTP. A challenge is consumed even when a proof fails.

Sign-in yields a one-hour read token in per-origin, per-tab sessionStorage. Requests explicitly send it as a header. The app issues no authentication cookies and no credential-bearing URLs. The signing key remains in the page's memory as a non-extractable Web Crypto key. Reloading a page preserves read access and requires sign-in again before a write. Closing the tab clears both the token and signing key. A local OS compromise or same-origin script compromise can impersonate the local account. Protect the local machine and serve only reviewed assets.

Each consequential POST requires another single-use challenge bound to its exact raw body digest, encoded path, read session and current action revision. It expires after 60 seconds. An authenticated write or inbound service delivery invalidates earlier pending write challenges. HTTP mutations are serialized in one process. Domain workflows must also validate their own durable resource revisions, since those revisions cover changes outside this HTTP runtime.

Sessions and challenges are held only in the current process. Restarting invalidates both, even with an unchanged account password. The database records its mode and human/rehearsal namespace. Opening it in another namespace or mode fails. An unscoped V3 database requires a fresh V4 workspace. The original V3 workspace remains the rollback artifact.

## Scripted rehearsal and service identities

The capture and rehearsal scripts create a temporary replay database and a random private credential. Their account is `scripted-test-reviewer`. The same UI or native challenge protocol authenticates that identity. Normal account enrollment forbids this reserved identity, and normal mode cannot open a rehearsal database. The disposable script identity demonstrates simulated review.

Inbound service callers use a distinct, pre-provisioned service key and `auth.service`. The server maps the key to its configured subject and emits `Principal(tenant, subject, "service")`. Its HMAC covers the runtime, exact origin, subject, POST path, raw body digest, timestamp and nonce. Duplicate nonces and old-runtime signatures fail. The domain layer must bind the authenticated subject to its allowed vendor and account. Caller-supplied sender metadata cannot establish that identity.

## Integration and verification

`create_app` accepts trusted embedding/test configuration for `approvals_enabled`, `origin`, `service_credentials`, and the explicit rehearsal options. The launcher verifies release evidence before enabling the gate. A route integration can implement `uptime.v4_routes.register_v4_routes(app, bench, auth)`, with `Depends(auth.actor)` for reads, `Depends(auth.reviewer)` for signed human writes, and `Depends(auth.service)` for signed service deliveries.

`uptime.auth_client.ReviewerClient` and `service_headers` implement native test clients. The browser exposes `window.uptimeAPI(path, payload)` for authenticated reads and signed writes. `tests/test_v4_authority_browser.py` launches real Chromium against two owned localhost ports, captures every request arriving at the sibling, attempts browser cross-origin access and native replay, and verifies a named positive-control approval. All traffic stays on the owned loopback listeners.
