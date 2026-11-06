# Phase79 — Existing monthly propositions and offline request export

This increment closes runtime setup and profile parity gaps within reviewed decisions73/74. It adds no contract grammar, compiler inference, fee authority, reviewer authority or automatic model retry. The lead authorized routine implementation without another architecture review round.

`monthly` retains its strict existing protocol. `monthly-propositions` explicitly selects the existing monthly proposal wire format and existing guarded proposition compiler fallback. `resource-month` retains its separate block protocol. The new profile is present in the complete request, proposal context, immutable result and install provenance. Exact permission for another profile does not authorize it; a resource manifest cannot be accepted under a monthly profile. Source text and receipt quotes are unchanged. Each profile pins its consumed semantic family.

A proposition-derived manifest still records `model_proposition_human_review_required`; normal SHADOW, independent tests, source interpretation acceptance, approval and activation remain separate. Merely selecting the new profile does not create interpretation acceptance. A strict clause accepted by the deterministic compiler remains deterministic under the opt-in profile, matching the existing legacy behavior. Missing governing fee or semantic authority still refuses monetary evaluation.

The public Juniper Reach source and authored proposal were frozen in `20412db` before implementation. They exercise known supported vocabulary, not unseen performance. Historical failed scores and receipts remain untouched. This code change updates existing source-code dependency pins; old jobs remain historical evidence and are not silently migrated to new authority.

The CLI export work is delegated to one actual bounded Claude Code worker with file tools only. Its completed contribution, exact session and tool inventory, and native verification will be appended after the worker exits. Export is an offline readable-request preparation step; approval and submission remain distinct actions.
