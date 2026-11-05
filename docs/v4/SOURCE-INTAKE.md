# Local synthetic evidence intake

Each offline-enrolled source gets an Ed25519 private key and one grant. The server keeps the public verifier and the exact claim scope that the source may describe. Each delivery needs a fresh signature. The browser cannot enroll a source or obtain its key.

## Provision one source

Run these commands in the project's Python environment. Use an operator-owned directory outside every Git repository. Its absolute physical path must have no symlink components. The tools require owner-only 0600 regular files, reject hard links and symlinks, and create new private credentials exclusively.

Create a separate synthetic scope JSON with these field names and your fixture identifiers.

```json
{
  "account":"test-account",
  "vendor":"Twilio",
  "contract":"signed-agreement",
  "service":"Twilio Messaging API",
  "component":"api-east",
  "invoice":"oct-bill",
  "incident":"oct-synthetic-outage",
  "currency":"USD",
  "month":"2026-10",
  "region":"east"
}
```

```sh
python scripts/provision_sources.py init --config /private/operator/sources.json \
  --tenant bears --mode replay --origin http://127.0.0.1:8765
python scripts/provision_sources.py add --config /private/operator/sources.json \
  --subject status.synthetic --source status --scope /private/operator/scope.json \
  --credential-file /private/operator/status-private.json
python scripts/provision_sources.py list --config /private/operator/sources.json
```

The operator selects one source role from `status`, `customer`, `billing`, and `vendor`. Each role accepts only the event kinds specified by the correspondence contract. A new subject or scope requires a separate grant. The full scope includes the month, invoice, incident, region and component in addition to tenant, account, vendor, agreement and service. The subject's public-key fingerprint and grant digest identify the exact authority the server verified.

## Launch and deliver

Use the same tenant, execution mode and listener when provisioning the reviewer and launching the workbench. The tenant belongs to this database. An older single-tenant V4 database can bind only to its original `bears` tenant. Production launches and external receivers are outside this local fixture channel.

```sh
python scripts/serve.py --tenant bears --mode replay --db /private/operator/workspace.sqlite \
  --source-config /private/operator/sources.json --port 8765 --enable-local-approvals
```

The explicit approval flag requires the release receipt. Observation-only launches reject evidence deliveries. A named reviewer must open the matching claim in the workbench before a source delivers its first event.

Save the correspondence JSON under a local path. The status example below supplies the body for a synthetic outage. The outer event must include `event_id`, the complete scope copied above, and this `body` object.

```json
{"kind":"status","start":"2026-10-08T01:00:00Z","end":"2026-10-08T02:00:00Z"}
```

```sh
python scripts/deliver_evidence.py --credential-file /private/operator/status-private.json \
  --claim inbox-source-intake-1 --event /private/operator/event.json
```

The client checks the local event schema and its grant, retrieves the current instance from the pinned numeric loopback origin, and signs the exact file bytes. Changing whitespace after signing invalidates the proof. Server verification covers runtime, tenant, execution mode, origin, subject, method, path, timestamp, nonce and body digest. The server independently checks every scope field and the source role before mutating an inbox. The command prints only the event ID, digest and server receipt time. A retry obtains a new transport proof and preserves the original event identity.

## Rotation and revocation

The running launcher reopens and validates the protected public grant file on each delivery. Rotation creates a fresh sender credential and invalidates the old key. Revocation takes effect on subsequent authentication, including for an unused signature made before the change. Missing or invalid configuration closes intake. Relaunch after adding a subject or changing its source or scope so the operator can bind the new subscription.

```sh
python scripts/provision_sources.py rotate --config /private/operator/sources.json \
  --subject status.synthetic --credential-file /private/operator/status-rotated.json
python scripts/provision_sources.py revoke --config /private/operator/sources.json \
  --subject status.synthetic
```

Configuration updates take an exclusive filesystem lock and replace the server file atomically. Prior process signatures fail after restart because each process chooses a new instance ID. Persisted event receipts enforce domain idempotency across restarts. Previously recorded evidence remains identifiable by its source at the time of receipt.

HMAC is confined to the default tenant's programmatic replay fixture channel. The launcher provisions only the asymmetric source channel. Named reviewers in sandbox mode or additional tenants need an independently issued [reviewer mandate](REVIEWER-MANDATES.md) for each exact action. The operator and local OS control key files, database contents and ownership of the pinned listener. This protocol authenticates the sender to the workbench and assumes the operator controls the local listener.
