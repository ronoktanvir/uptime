# Public proposal runtime

The optional queue connects approved public source requests to normal application review. It does not enable customer processing or confer adapter activation, human review, evidence authority, credit, vendor communication or Ramp posting permissions. The operator remains responsible for approving genuinely authorized public material; code matches the exact approved source/request but cannot establish whether an operator classified confidential content truthfully.

Keep runtime configuration and its approval catalog outside Git, in an operator-owned `0700` directory with `0600` files. The configuration has no HTTP counterpart:

```json
{
  "version": 1,
  "executable": "/absolute/path/to/claude",
  "approvals_path": "/absolute/private/path/public-approvals.json",
  "kinds": ["vendor", "correspondence"]
}
```

Create an empty approval catalog with `version: 1`, `limits: {"daily_jobs":20,"daily_budget_usd":"20.00"}` and `approvals: []`. Enable only the kinds needed. Start the existing local server with `--public-proposal-config /absolute/private/path/config.json`. The configuration uses the existing authenticated Claude Code installation and the reviewed tool-free profile. No credential is read into a prompt, copied into this configuration, or stored in Git.

The existing authored Northwind workspace can use the same protected configuration with `scripts/setup_northwind.py --directory /absolute/workspace/path --resume --serve --public-proposal-config /absolute/private/path/config.json`. Its financial ledger and existing source identity are preserved. Model permissions still require each exact source request; resuming a workspace does not approve new inputs.

The application exports the complete request and its binding after normal account/source permission checks. Its JSON has `tenant`, `subject`, `kind`, `target`, `context_sha256`, `request` and `source_references`; each source reference has `reference` and `sha256`. The request includes model, prompt, schema, source bytes and pinned transport settings. Source whitespace is preserved. Overlays and private fee data are not part of vendor generation. A request export is not permission to send it.

For vendor requests, prepare the complete export with `scripts/public_proposals.py export-vendor --document /public/vendor.json --config /protected/config.json --output /protected/exports/request.json --tenant WORKSPACE --subject ACCOUNT --target VENDOR --profile monthly`. The protected output directory must already exist with mode0700, and the output file must be new. Supported named profiles are `monthly`, `monthly-propositions` and `resource-month`; each requires its own exact permission. With automatic family selection (D05), use `--profile auto`. It writes one export per supported family beside the output path, and each must be reviewed and approved separately ([runbook](D05-UNSEEN-VENDOR-RUNBOOK.md)). Export makes no model call and grants no permission. [Full operator procedure and limits](decisions/ADR-0079-monthly-profile-and-offline-export.md)

Review and explicitly authorize an authored-public request offline:

```sh
uv run --locked python scripts/public_proposals.py show /private/path/request.json
uv run --locked python scripts/public_proposals.py approve /private/path/request.json \
  --approvals /absolute/private/path/public-approvals.json \
  --approved-by engineering-operator \
  --expected-request-sha256 THE_REVIEWED_COMPLETE_REQUEST_HASH \
  --confirm-authored-public --hours 24
```

The operator CLI writes the full readable request, identity, source references, approval time and expiry atomically. It grants only model invocation; `approved_by` is an operator record, not a claim of ACTUAL_HUMAN semantic or financial approval. The app has no permission-grant endpoint. New sources, settings or attempt nonces need new exact approval. Expired and revoked requests cannot start; an already-running request may finish, and completion after expiry is recorded.

Generation reserves a durable job before responding. Signed POSTs can create jobs; GET polling cannot invoke a model. The same tenant/kind/target/context/request tuple resolves to the same job for the submitting subject. Other subjects cannot read or reuse it. A bounded private provider-response record preserves rejected attempts for diagnosis; the product receives only accepted typed results or safe failure codes.

QUEUED is reserved without dispatch; RUNNING is committed before provider invocation. SUCCEEDED, REFUSED, CANCELLED and UNCERTAIN are terminal. A local process lock prevents concurrent queue owners. On restart, queued work is cancelled and running work becomes uncertain. No automatic retries occur. An explicitly approved new attempt nonce creates a separately recorded attempt; renewing an approval alone cannot reset a terminal job. The maximum two workers serialize each provider instance to preserve its receipt and refusal state. Daily reservations cap invocation count and declared budget; the provider's advertised budget is not a hard billing guarantee.

Use local storage only; this process-lock/SQLite design is not a distributed worker system or a supported network-filesystem deployment. Preserve the database and its `.public-proposals.lock` pathname. Removing the optional config disables new model generation. Graceful shutdown cancels pending work, waits for bounded in-flight calls, and preserves outcomes. Never delete uncertain records as a retry mechanism.

Candidate attachment and job completion are separate transactions. A crash can leave an inert, request-linked dispute candidate beside an UNCERTAIN job. That candidate still requires independent reading, semantic review and existing action gates. Model-reported identity checks, structural grounding and regression passes do not establish semantic correctness or production readiness.
