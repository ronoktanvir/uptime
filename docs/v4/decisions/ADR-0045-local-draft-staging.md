# ADR 0045 — Local draft intake without approval authority

Status is implemented with external and acceptance limits recorded in STATUS.md.

## Decision and alternatives

Permit only exact signed candidate intake, independent draft tests and pure shadow preview for an enrolled reviewer while consequential deployment gates remain closed.

The application can accept and inspect an untrusted draft without promoting a version, creating an active entitlement, changing an approved vendor or sending correspondence. Enrolled viewers retain read access only.

The original alternatives, costs and falsifiers remain in [the decision packet](packets/45-local-draft-staging.md).

## Independent review and disagreement

Actual model is `claude-opus-5-5`, session `a574e177-f9c1-4d6d-b8d4-de2f8e331003`. The packet SHA-256 is `b15acdd52885ae1b6e785b90061a6f8c04c1d037fc52b8853de37eb1b9fc086a`. The full [review receipt](reviews/45-local-draft-staging.json) retains the reply and model identity.

Opus's bootstrap-dependency objection supports the narrow path. Candidate install previously suspended an active adapter, so the draft capability rejects any publication history atomically. The server enforces capability separation even if browser controls are altered.

## Verification and rollback

133 focused checks and independent security before/after 118/118 at 8385787, plus body tamper, origin replay, approved-history, viewer and action-path negatives

Remove the draft path allowlist. Retain drafts and evidence, and resume read-only inspection while regenerating any affected candidate.
