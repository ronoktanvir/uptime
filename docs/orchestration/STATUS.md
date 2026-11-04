# Release status

**Local integrated application verified.** CP0 through CP5 passed at their documented local scope. CP6 has a rehearsed and decoded 120-second fallback. The real sandbox website required an interactive sign-in. The API grant allowed real bill reads but omitted draft writes. See CHECKPOINTS.md for the precise gate outcomes.

The release suite passed 475 Python tests and seven browser-client tests. The Python test runner emitted one dependency deprecation warning in FastAPI’s TestClient integration. The code uses the locked environment. The release does not rely on live vendor communications or a hosted model at runtime.

An independent actual Opus review was recorded for each of thirteen decision packets, plus a model identity smoke check. The onboarding extraction and public Twilio extraction/investigation/guide plan were separate genuine model runs. All coding workers ended; no agents are asserted to run after this session.

## Verification evidence

- `evidence/release.json`: checkpoint suite results and film checksum.
- `evidence/rehearsal.json`: deterministic service outcomes in a disposable database after restart.
- `fixtures/ramp/verified.json`: measured API scopes, IDs, dates, readbacks and observed empty credit dataset.
- `fixtures/disputes/oracle/` and `fixtures/disputes/traces/`: precommitted predictions and independently generated receipts/outcomes.
- `fixtures/onboarding/`: actual model extraction, separate tenant overlay, shadow and term gold.
- `docs/demo/film/`: captioned offline walkthrough, scene manifest and five representative stills.
- `TASKS.md`, `DECISIONS_INDEX.md`, `BLOCKERS.md` and `RUNBOOK.md`: staffing history, reviews, limits and restart.

## Chronological gate log

### Initial inventory
CP0. The provided workspace had only empty work/ and outputs/ directories. No Git root, manifests, tests, branches, worktrees or implementing files were present. All V3 handoff files are preserved in docs/uptime-v3. Local sandbox credential path is readable, mode 0600. Claude Code 2.1.318 authenticated and returned OPUS_READY with modelUsage claude-opus-5-5. Native subagent harness exposes three worker slots beside the lead. Codex CLI 0.156.1 authenticated separately. No live service or persistent scheduler installed by this project.

W1 merged at 1a58b6e. Verified two same-ID bill reads, no draft grant, empty credit response. Combined W1/storage/contract/model suite: 42 passed; secret comparison passed.

W3 merged at 4c7fdd2. Full then-integrated Python gate: 101 passed in 17.22s.

W4 merged at 14c8274. Full then-integrated Python gate: 152 passed in 0.36s.

W5 merge fbaafb3: 179 passed in 0.60s.

W2 merge dcd8535: 251 passed in 0.53s.

W6 merge 43140f6: 350 passed in 0.49s.

W7 merge 8a6a627: 350 passed in 0.45s.

EXT merge 88944c8: 382 passed in 0.54s.

W8 merge 6f578b3: 452 passed, 1 warning in 8.43s.

W8-film merge 99313b1: 452 passed, 1 warning in 7.69s.

W1 provenance follow-on cc16482: 464 passed, 1 warning in 9.32s.

### Portable release verification

A clean Git archive was extracted outside the synced Documents folder. A fresh locked environment passed all 475 Python tests and all seven Node tests. The service rehearsal matched the committed JSON after restart. A second real browser run verified desktop and 390-pixel mobile views, case, onboarding and policy navigation with no browser errors or external requests. Its first attempt exposed a modal-navigation bug in the QA driver; closing the inspector before navigation repaired it. The browser proof is in evidence/browser.json and the mobile capture is in docs/demo/film/mobile-workbench.png. All 15 supplied files matched the source package byte-for-byte.
