# ADR-0035: Ramp authorization and demo

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **BLOCKED — customer install and native write proof**.

## Decision and alternatives

Keep app REST identity, optional human CLI identity, customer OAuth installation and confirmed provider effects distinct in both operation and demo claims.

Human CLI substitution can expose broader authority and blur accountability. Server app credentials are auditable but grant-limited. Explicit simulated native responses allow rehearsal without falsely representing writeback.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/35-ramp-authorization-and-demo.json](reviews/35-ramp-authorization-and-demo.json); its sanitized input is [packets/35-ramp-authorization-and-demo.md](packets/35-ramp-authorization-and-demo.md). Receipt time: `2026-11-05T00:20:13.889815+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `71e36e16-9437-4803-8767-c05b0312deff`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus agrees with the separation but requests exact token receipts, negative enforcement evidence, sandbox URL checks, same-ID readback and a timed demonstration. It does not verify the provider claims in its response.

**Root position and reconciliation:** Accept the evidence standard, with no unauthorized write probe. An unauthenticated admin screen cannot explain omitted grants. CLI availability is not an authenticated customer integration; neither client credentials nor local operator login establishes a customer OAuth installation. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

RAMP-FEASIBILITY and ramp-bill-grants preserve observed read scopes and missing reported write grants. Feasibility reports the CLI sandbox profile unauthenticated and no multi-business installation. Native workflows remain bounded code/mock evidence.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/ramp.py](../../../uptime/ramp.py)
- [uptime/ramp_workflow.py](../../../uptime/ramp_workflow.py)
- [docs/v4/RAMP-FEASIBILITY.md](../../../docs/v4/RAMP-FEASIBILITY.md)
- [docs/v4/evidence/ramp-cli.json](../../../docs/v4/evidence/ramp-cli.json)

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_ramp.py tests/test_ramp_workflow.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** A production default, silent human credential substitution, invented native URL or simulated response labelled live falsifies the boundary. Customer installation and writeback remain blocked without their distinct consent and actual receipts.

## Versioned rollback

Disable optional CLI/native paths, retain authorization and rehearsal records, and require fresh object-specific authority for future effects. Do not change app scopes, approval chains or registrations as rollback. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `08bf2dc6bd042b0009d3848818569a4c12d5a043adbd59a627e77e5a5a22650f` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `e9b423cc13fe77fa2ddbfa598d08a2a17f792a219cbcf6a6dff08e2bbd43b497`.
- Review-prompt SHA-256 recorded by receipt: `58e8bead7f5cf3f3af78e5c59f3254c87fbf18d1c60abf367db646bf361eebb5` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
