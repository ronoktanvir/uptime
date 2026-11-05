# Independent Gates 2 and 3 acceptance

Status: **NOT RUN**. This document does not certify either gate.

The independent fixture was frozen at `9364cd2bf2023adbc1a6f99bc275ac1ae36476ee` before product inspection. The QA worktree started from `940cd45`. Ownership is limited to this document, `scripts/blind_acceptance.py`, and `tests/test_blind_acceptance.py`; product behavior and frozen inputs are not edited here.

Private synthetic records stay in shell-local memory and disposable local databases. Exported receipts contain hashes, counts, feature categories, fail codes and expected/observed money only. Neither exception text nor HTTP bodies are exported. Gold comparison follows observation capture. Missing execution, unknown amounts and numerically wrong amounts remain distinct.

Execution must use real signed loopback HTTP, normal vendor intake and independently signed inbox sources. The source checkout is selected with `--source`. Public model extraction is supplied by the root operator through `UPTIME_PUBLIC_EXTRACTIONS`; `UPTIME_MODEL_PROPOSITIONS=1` is explicitly authorized. This runner does not invoke a model or construct extraction proposals.

The frozen interchange stores case input selectors together with expected results. Input-only projection requires the operator's authorization or a separately supplied input plan; expectations remain deferred until observations exist.

A rejected or unavailable public extraction blocks contract acceptance. A separate denial exercise against a previously supported general adapter can establish dispute generality only; it cannot make unsupported frozen terms active or turn unavailable money into agreement.
