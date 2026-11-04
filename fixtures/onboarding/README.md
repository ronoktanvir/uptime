# Atlassian onboarding replay

The local lab opens in SHADOW. Its 14 synthesized tier-boundary tests, 23 independently specified term checks and 18 held-out scenarios run against a pinned candidate. No packaged fixture supplies a human approval.

## Reproduce

Run `uv run --locked python -m uptime.onboarding` to print the generated public manifest and threshold tests. Output must match `fixtures/onboarding/generated_candidate.json`. Run `uv run --locked pytest tests/test_onboarding*` for shadow, lifecycle, race, isolation and security tests.

The public source acquisition used Atlassian’s [current SLA](https://www.atlassian.com/legal/sla), its [official April 30, 2026 PDF](https://dam-cdn.atl.orangelogic.com/CDNLink/AT12MQRY.pdf), and [support process](https://support.atlassian.com/subscriptions-and-billing/docs/service-level-agreement-for-atlassian-cloud-products/). The legal PDF preserves both Enterprise table columns. Jira’s [public status page](https://jira-software.status.atlassian.com/) provides context only.

The recorded tool-free Claude Opus 5.5 session extracted just these public terms. The record includes the UTC capture time, model, session, input and output hashes, source URLs, and source digests. To **stage** a fresh extraction, use `uv run --locked python -m uptime.onboarding_extract` with a local authenticated Claude CLI and Poppler's pdftotext. The command prints JSON and does not install it. The source fetch fails if the official SLA no longer links the pinned PDF. Offline regeneration reads the accepted extraction and requires no model, network or external credentials.

## Scope and approval

This prototype implements two Jira browser plans on unmodified public, direct-purchase terms. It uses a synthetic customer overlay and a confirmed, fully allocated affected-product USD monthly line. Shadow measurements stand in for Atlassian's own full-month, exclusion-adjusted monitoring. An eligible sample reports a modeled service credit. No case here represents a vendor decision, credit application or cash recovery.

The monthly usage interval is UTC. A complete, separate compensation request may be received through the 15th of the next month. The support process also calls for a technical ticket during the incident. A challenge concerns the **amount already posted** to the ticket. A planning date can be computed only with an explicit business zone and confirmed holiday calendar. The helper counts three subsequent weekdays, excluding holidays. No exact cutoff time or waiver is inferred.

`get_lab(connection, authenticated_principal)` returns current state. `act(connection, authenticated_principal, returned_action_id)` accepts only the displayed action bound to the candidate, tenant, overlay, test corpus and lifecycle state. The server must establish the role and tenant. Only the interactive `reviewer` role can approve, activate, revoke or roll back. First-version rollback disables the adapter. A later implementation revision can restore the last previously approved compatible version. Changed source terms, overlay or test basis clear prior approval, and an unsupported extraction quarantines the candidate. Local SQLite stores append-only events and immutable manifests. A database administrator remains outside this local threat model.

The unit tests create synthetic reviewer principals in isolated databases to exercise these transitions. The default workspace contains no recorded human approval. Updating any public capture or changing code requires normal repository review. This demo has no automatic source watcher, vendor transmission, or production deployment.
