# Person-operated demo path — November 7

The team approved authored contract data and oral disclosure, a teammate operating normal adapter controls, and a human-posted Ramp note. These decisions prepare a credible demonstration; they do not establish customer execution, commercial reviewer authority, independent generalization or actual Ramp recovery.

## Current evidence and remaining steps

| Step | Observed result | Remaining requirement |
|---|---|---|
| Northwind terms and financial flow | Existing source-linked engines produce January $2,400, February ineligible, March unknown SLA and separate $1,000 price finding. April $11,000 − $2,400 = $8,600. Focused unchanged suite: 105 passed, 1 warning in 59.32s. | Exact expandable clauses and decimal explanations are implemented. Fresh presentation state is ready; the old completed workspace is preserved. |
| Teammate adapter review | Ronok Tanvir selected as reviewer; account name `ronok-tanvir`. Separate normal workspace is prepared in SHADOW;3 source controls pass. No action has been signed as Ronok. | Human source interpretation/approval/activation/rollback. Existing signed release gate is unsatisfied; no current release_attestation.json exists. Prepared sign-in and SHADOW state do not close this blocker. |
| Ramp note | Fresh read verified business 1569e402-460e-4952-adad-9df27db628a0 and bill f74ba12c-95d0-582d-9f62-26d8057d1d37, USD840.00. Initial complete discussion was empty. The person then posted the exact note; two complete API reads verified comment 376563cf-950c-409d-b3d8-a68599c45fa0, exact text and timestamp 2026-11-08T01:46:45Z. The verifier attempted no write. | Human posting and optional same-ID read-back are complete. Screenshot shows note/author/relative time; it does not include the browser URL. This is human-posted proof, not Uptime-origin API write proof. |
| Continuous demonstration | Existing Northwind eleven-step browser/socket flow is preserved. | Fresh 11-step socket run completed with unchanged duplicate actions and April $8,600. Manual Ramp note is verified. Human promotion remains release-gated; the combined 120-second flow has not been filmed. |

The current local release policy requires independently signed regression, security/financial, unseen-vendor and unanticipated-dispute evidence plus a separate human release witness, bound to current source and fresh within 24 hours. A narrower local-only exemption would change that policy; it has not been implemented or silently approved. Unit tests with a mocked gate do not supply release evidence.

## Human Ramp action

Open [the verified demo bill](https://demo.ramp.com/bill-pay/bills/list/f74ba12c-95d0-582d-9f62-26d8057d1d37). In its discussion, a person posts:

> Uptime review: governing agreement or usage evidence is missing for this bill. Unable to verify charges against contract terms. Please attach the signed agreement or usage records.

Capture the author, timestamp and full bill URL. Do not add constructed $40/$800 figures or claim payment was stopped. This bill is not the authored Northwind invoice. A read-back proves only what the API returned at that time, not who clicked Post or that Uptime wrote it.

The public [Ramp comment API](https://docs.ramp.com/developer-api/v1/api/comments) supports a paginated resource read; the [machine-readable reference](https://docs.ramp.com/llms-api.txt) describes ID, message, user_id and created_at. Read-back uses bills:read; business:read confirms the selected installation. No additional write scope or different credential is requested.

Automatic approval review rejected the agent-run native-posting retest as “possible cybersecurity risk.” It remains disabled. No model, browser or alternate credential may be used to reroute that action. The optional fuller person-run route remains in [NATIVE-OPERATOR.md](NATIVE-OPERATOR.md) and still needs its protected installation, issuer mandates and signed release.

## Presenter disclosures

“This contract and its usage records are authored for the demo.”

“Ronok Tanvir is acting as the contract reviewer.” Say this only when Ronok operates the controls. Do not describe scripted history as Ronok's actions.

“The connected Ramp bill needs its own agreement; this authored contract is not evidence against it.”

“The credit application shown here is in Local ledger, not money recovered in Ramp.”

Keep these explanations in the spoken presentation and handoff. Product screens use ordinary clauses, amounts, reviewer records and accurately named destinations without added demo badges or hidden mode tags.

## Evidence boundaries

Onboarding and dispute preparation continue in parallel within this small patch. Frozen evaluation worktrees84–86, known scope-identity defects and broader team decisions remain preserved and unresolved. One real Opus5.5 criticism of this path is recorded in [decision87](decisions/ADR-0087-person-operated-demo-path.md); it does not replace tests or human action.


## Running local sessions

- Northwind presentation: http://127.0.0.1:8776/ — fresh, unfiled state; scripted account and its private key are under the separately prepared runtime directory.
- Ronok review: http://127.0.0.1:8777/#vendors — account `ronok-tanvir`; key at `$HOME/.local/share/uptime-engineering/runtime/ronok-review-87/reviewer.jwk`. Only Ronok should operate the real review steps. Current status: RELEASE_PENDING.
- Current progress map: http://127.0.0.1:8781/ — the existing 8780 listener serves a different checkout at `$HOME/uptime` and was left untouched.

[Fresh Northwind socket proof](evidence/demo-path-87/northwind-socket.json) · [Human Ramp note read-back](evidence/demo-path-87/human-ramp-note.json) · [User screenshot observation](evidence/demo-path-87/human-ui-observation.json) · [Actual Opus coding contribution and root corrections](evidence/demo-path-87/opus-coding.json).

These are local processes, not a deployed service or a promise of continued agent execution. Restart with the setup commands in [NORTHWIND-WORKFLOW.md](NORTHWIND-WORKFLOW.md), using the existing directory and `--resume` to preserve state. The current prepared Northwind directory is `$HOME/.local/share/uptime-engineering/runtime/northwind-presentation-87`.
