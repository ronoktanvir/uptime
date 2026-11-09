# Strict-source remediation and explicit monthly compiler support

Status: implemented under the user-resumed November 9 workstreams; integrated validation pending.

The released diagnostics identified nine generic wording classes that the strict monthly parser did not support. We extend only statements of existing supported semantics, preserving exact values and source spans. Alternatives were leaving the parser unchanged (sustained setup refusals) or letting a model infer arbitrary financial meaning (unsupported eligibility risk). Public-model proposals remain untrusted and require deterministic complete-source validation plus the existing human interpretation review.

A real Claude Code `claude-opus-5-5` xhigh coding worker implemented the grammar and authored controls; [receipt](../evidence/onboarding-finish-20261109/worker-completed.json). Parent analysis disagreed with treating bare “until” as inclusive and changed it to an explicit-inclusion requirement. The parent also fixed source scope in proposition fallback and requirement-card field classification. No second advisory council was created. The optional monthly marker was separately user approved during this work and implemented by the parent in both compiler paths. It never derives an incident waiver from silence.

Verification: 433 focused tests passed, 1 existing warning in 3.17s. Exact changed existing test and retained failures are in [the ledger](../TEST-CHANGES-onboarding-finish-20261109.md). Whole-source contradictory incident requirements refuse. Monetary boundaries distinguish tier eligibility, exact fee basis and exclusive filing cutoff; unknown evidence yields no amount. Development tests are not unseen evaluation scores.

Rollback: revert the compiler/model/diagnostic change and explicit marker helper together with the integrated monthly core as needed, then re-run the locked suite. The reviewed-semantics hash must change on rollback too; do not restore stale activation authority. No Ramp action, reviewer signature or historical evaluation record is changed.
