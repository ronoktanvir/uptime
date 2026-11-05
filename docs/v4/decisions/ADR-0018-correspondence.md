# ADR-0018: Correspondence

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL**.

## Decision and alternatives

Treat independently signed inbound correspondence as untrusted evidence; propose intent, deterministically check scope and current terms, bound supplements, and escalate ambiguity.

Hardcoded scenario replies cannot cover novel wording. Unconstrained model correspondence risks invented entitlement. Template-only outbound text with a reviewed clause library reduces generation risk but still requires the same scope, evidence and authority checks.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/18-correspondence.json](reviews/18-correspondence.json); its sanitized input is [packets/18-correspondence.md](packets/18-correspondence.md). Receipt time: `2026-11-05T00:20:29.080005+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `69828812-37c4-400c-a2a4-9b4f3be1d3ea`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus locates the main risk in validation, citing amount/currency/component confusion, clone submission and redaction leakage. It challenges simulator independence and legal time-bar overrides, and adds negation, stale quote, replay and redaction tests.

**Root position and reconciliation:** Accept that text anchoring alone does not establish a valid award. A timely filing may rebut a simulated mistaken time-bar only under the controlling verified clock; it is not authority to override a real vendor or legal deadline. No real vendor communication is enabled by this decision. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

Correspondence resource joins derive facts from scoped events; filing receipts and supplements are explicit. Shared claim reservations now address cross-route duplication. Audit evidence is bounded synthetic protocol coverage, not a real inbox integration.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/correspondence.py](../../../uptime/correspondence.py)
- [uptime/correspondence_reason.py](../../../uptime/correspondence_reason.py)
- [uptime/correspondence_resource.py](../../../uptime/correspondence_resource.py)
- [uptime/claim_identity.py](../../../uptime/claim_identity.py)

Audit: [durable audit results](../audit/RESULTS.md), especially its source pin, unavailable browser observations and failed release flags. This report does not certify the later inspected main revision.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_correspondence.py tests/test_correspondence_resource.py tests/test_disputes_v4.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A mismatched component/currency accepted as an award, unknown wording becoming a claim, known exclusion permitting initial filing, or private sentinel reaching the simulator falsifies the design. Generality and real sender custody require separate evidence.

## Versioned rollback

Disable intake/dispatch for the affected source or family, preserve messages and observed_at receipts, quarantine disputed results and append corrected evaluations. Never erase a send reservation or resend an uncertain delivery. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `83ad78c8e983ba140bb35fb957aa1171f4f12fa580829cff64cf6b0050cb7c5b` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `0884b2b2593b41770f4b646c0b7eb47713f1ee2b637c5e1058d5a711b4ff20b9`.
- Review-prompt SHA-256 recorded by receipt: `9fdc1d821148d4cee0c77bfaa97889ef854cb3eeacf054b30385b63ec0bf612b` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
