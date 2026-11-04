# Uptime V3 — Handoff package

**Ready to give to a Codex coding chat.** This is a new specification and orchestration package, *not* a claim that coding subagents were launched or the application's repository was modified. The existing V2 documents remain unchanged and preserved in the previous package.

## Quick start

1. Attach this ZIP (or extract it into your existing Uptime repository under a `docs/uptime-v3/` folder), along with access to the actual codebase, to your Codex chat.
2. Copy the entire text of `PASTE_INTO_CODEX.md` into the chat.
3. Follow `Uptime_V3_Credentials.md` to store **sandbox-only** Ramp secrets on the local machine; keep them out of the chat/repo. If Codex runs in the cloud, use approved cloud secret injection instead.
4. Confirm the coding environment supports real parallel agents and actual Opus 5.5 access. Keep an ADR trail and do not pretend model consultations happened.
5. Let the orchestrator build against its actual repo and permissions. It must keep W3 Vendor Onboarding and W4 Dispute/Appeal equally staffed and active.

## Files

- `PASTE_INTO_CODEX.md`: paste-ready autonomous build instruction, with product scope and guardrails.
- `Uptime_V3_Orchestrator_Handoff.md`: authoritative full orchestration specification; staffing, decisions, permissions, milestone reporting and hard engineering requirements.
- `Uptime_V3_Product_Technical_Spec.md`: revised full product and engineering blueprint, including original context, critiques, consent requirements, tests and vendor examples.
- `Uptime_V3_Product_Engineering_Blueprint.docx`: readable Word version of the complete product/engineering spec.
- `Uptime_V3_Work_DAG.md`: Mermaid implementation DAG + checkpoints + work ownership.
- `Uptime_V3_Work_DAG.png`, `.svg`, `.dot`: rendering and editable source.
- `Uptime_V3_Decision_Governance.png`, `.svg`, `.dot`: Opus consultation and human authorization process diagram.
- `Uptime_V3_Credentials.md`: safe Mac commands and remote-agent access warning.
- `Uptime_V3_ADR_Template.md`: decision record for real Opus consultations.
- `AGENTS.md`: optional instructions to copy to repo root if Codex supports repository agent instructions.

## What is not done here

No application code was touched; there was no code repository provided in this chat. No Claude agent or Codex subagents were actually launched in this response. The Ramp sandbox credentials are not known or stored by this chat. The handoff instructs your Codex implementation agent to inspect, implement, test and report evidence.

## Official references

- https://docs.ramp.com/developer-api/v1/guides/getting-started
- https://docs.ramp.com/developer-api/v1/scopes
- https://platform.claude.com/docs/en/models/opus-5-5/overview
- https://developers.openai.com/api/docs/guides/agents-api/multi-agent
