# ADR-0032: Ramp workflow surface

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL — local adapter; native delivery blocked**.

## Decision and alternatives

Prepare exact informational bill comments first, model procurement metadata only with a genuine matching trigger, and keep financial approve/reject separately blocked.

Comments are least coupled to workflow but do not stop payment. Metadata mutates trigger presentation and requires matching lifecycle context. Approve/reject affects workflow and requires additional authority; unrelated object comments are not substitutes.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/32-ramp-workflow-surface.json](reviews/32-ramp-workflow-surface.json); its sanitized input is [packets/32-ramp-workflow-surface.md](packets/32-ramp-workflow-surface.md). Receipt time: `2026-11-05T00:20:00.925398+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `90ca5d5f-bd03-497b-b20c-15d688b649ec`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus recommends comments first, metadata prototype and modeled decisions. It challenges undocumented endpoint assumptions and races in comment-list readback, and requires crash/reset/service-key tests.

**Root position and reconciliation:** Accept the staged scope and readback-race objection. A durable outbox can prevent blind retry but cannot manufacture provider exactly-once behavior. Native Bill Pay and Procurement are distinct; never infer a trigger from a bill. No positive native writeback receipt is present. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

ramp_workflow implements scoped provider, exact plans, durable state and reconciliation. A separate native_bridge worker commit 0072b72 implements an explicit mounted binding but is not in inspected main 1087804; its reported MOCK_HTTP tests are not provider receipts.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/ramp_workflow.py](../../../uptime/ramp_workflow.py)
- [uptime/ramp_installation.py](../../../uptime/ramp_installation.py)
- [uptime/ramp_webhooks.py](../../../uptime/ramp_webhooks.py)

Worker evidence: `/Users/ronoktanvir/.local/share/uptime-engineering/tasks/INTERFACES-native-binding.md`; native_bridge commit `0072b72b75017dc82233e4d0c2084fd271d08299`, `uptime/ramp_native_binding.py`. Worker results are reported evidence, not a root integration gate.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_ramp_workflow.py tests/test_ramp_workflow_webhooks.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Crash after POST causing a duplicate, reset allowing stale metadata, wrong service_key accepted, or a bill without a trigger invoking procurement mutation falsifies the design. Closing live delivery requires authorized same-thread comment readback.

## Versioned rollback

Disable the optional binding and preserve outbox unknown states. Reconcile with reads before any retry; reverting local code does not delete a remote comment or undo a workflow decision. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `5a65e137ef09cd77894074ffff67db50793f0b15d5e52035ff9aa55eacc866f6` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `5a31f537ee98da8e2c19e1afe49cbcb21e9fa5c33f21caadf78a340e96335533`.
- Review-prompt SHA-256 recorded by receipt: `f7709a5e6475d3ab0b3e9bcfab2dc957e57909b513017363a0804d88c719ae54` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
