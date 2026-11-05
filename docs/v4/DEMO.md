# Ramp-first two-minute demo

## Current Northwind walkthrough

The current interactive walkthrough uses the ordinary finance workbench and the signed contract, dispute and financial services. Its customer documents, reviewer display name, vendor messages and ledger are authored demonstration inputs. State this orally before the presentation. The product uses ordinary document references and financial states; the write destination is accurately named **Local ledger**. This run is not native Ramp write or actual recovered-money proof.

Start a fresh private workspace outside the checkout (choose a new directory name for each new presentation):

```sh
uv sync --locked
uv run --locked python scripts/setup_northwind.py \
  --directory "$HOME/.local/share/uptime/northwind-session-001" \
  --origin http://127.0.0.1:8776 --serve
```

Open `http://127.0.0.1:8776`, sign in as `scripted-test-reviewer`, and select `scripted-reviewer.jwk` from that directory. Do not copy the key into chat or Git. If the page reloads, the in-memory signing key is discarded and the next write asks for sign-in again. To restart without resetting state, use the same command with `--resume`.

| Time | Show and do | Explain |
|---|---|---|
| 0–25 seconds | March price review, governing amendment and January/February/March evaluations | The March cap is USD 11,000 against a USD 12,000 invoice: USD 1,000 requires review before payment. January earns USD 2,400; February is ineligible; incomplete March evidence prevents an SLA estimate. |
| 25–45 seconds | Approve January claim → File January claim → Receive vendor response | Filing preserves the exact contract and evidence. The vendor requests the missing resource log; a denial does not automatically end the case. |
| 45–75 seconds | Attach requested log → Verify supplied log → Approve response → Send response | The new artifact and separate verification must satisfy the requested proof. Authorization and the follow-up clock remain enforced. |
| 75–100 seconds | Receive credit decision → Post to Local ledger → Receive next invoice → Apply credit to eligible invoice | Award, posting and application are distinct. The same verified credit is applied once to April's USD 11,000 invoice, leaving USD 8,600. The March finding remains unresolved. |
| 100–120 seconds | Bill reconciliation and CalyxQuay contract coverage; expand Agreement & review record | Show the credit/application IDs, adapter hash, shadow/review/activation/rollback history and actual reviewer principal. Ramp remains the intended financial system of record; native publication and real credit synchronization are separate uncompleted proof gates. |

The 11-step socket receipt checks duplicate requests and independent readbacks. The normal browser also completed all 11 steps. A restart readback preserves the final IDs and balances. [Execution evidence](validation/northwind/browser-verification.json) · [Socket receipt](validation/northwind/final-socket.json) · [Complete screen](validation/northwind/browser-applied.png)

For a deterministic fallback, run the signed client against an owned running fresh workspace:

```sh
uv run --locked python scripts/rehearse_northwind.py \
  --directory "$HOME/.local/share/uptime/northwind-session-001" \
  --receipt "$HOME/.local/share/uptime/northwind-session-001/socket-receipt.json"
```

It follows server-issued actions and records actual results; it does not manufacture an expected award. An already completed workspace yields zero new actions. The saved complete screen and receipt are the fallback if the local server is unavailable. The existing 120-second video below is an older, separate demonstration and has not been regenerated to depict Northwind.

## Historical recorded film

`scripts/film_ramp_v4.py` captures the normal application, starting at `#ramp`, in a fresh disposable replay database. Thirteen actual browser screenshots become exactly 120 seconds of H.264 video through the existing `film_demo.py` ffmpeg encoder. The captions sit below the untouched application image. The video is silent; the spoken script below is for a live presenter. There are no stock assets, replacement screens, Ramp embeds, provider calls, or live writes.

## Reproduce and verify

Run from the checkout being filmed. Paths derive from the script location, not a developer’s home directory; `--output` accepts an absolute destination directory. Dependencies must be installed before the offline capture:

```sh
uv sync --locked --group dev
uv run --locked playwright install chromium
# Install ffmpeg using your system package manager; on macOS:
brew install ffmpeg
uv run --locked pytest tests/test_film_ramp_v4.py -q
uv run --locked python scripts/film_ramp_v4.py --check --output /tmp/uptime-ramp-v4-check
uv run --locked python scripts/film_ramp_v4.py --output docs/demo/v4
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,pix_fmt,duration,nb_frames -of json docs/demo/v4/walkthrough.mp4
```

Use a new or empty output directory for each run. `--browser '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'` selects an installed browser instead of Playwright Chromium. In a restricted worker, set `UV_CACHE_DIR=/tmp/uptime-demofilm-uv` if the normal uv cache is inaccessible. A worker without loopback socket permission must hand execution to the root process; it must not substitute mocked screenshots.

`--check` executes the same authenticated browser interactions and runtime assertions, producing actual screenshots and `evidence.json`, but no MP4. Normal rendering also produces `manifest.json` and internally requires ffprobe to report H.264, yuv420p, 1280×900, 120.0 seconds and 2,880 frames. `evidence.json` records view names, durations, checked native ID, capture digest, source kinds, checked amounts, and simulated ledger stages. It excludes credentials, requests, cookies and raw API dumps. Final rendering, visual inspection and independent ffprobe verification belong to the root integrator. Run `uv run --locked pytest` after merging.

The script writes the exact P-256 rehearsal JWK to a mode-0600 file in its temporary directory and uploads it through the normal account/credential-file login form. The server and browser use the same generated rehearsal secret. The account is `scripted-test-reviewer`, not a human approval. The credential, database and browser profile are disposable. Python transports permit loopback connections only; browser requests are restricted to the exact local origin and WebSockets are closed. No HAR, trace or browser console is saved.

## Evidence and UI limits

The explicit designation comes from committed `fixtures/ramp/native-cap-binding.json`: native bill `ae98c421-2c70-5586-8719-4fe8acd7ceda`. Runtime checks require its bound capture digest, USD 840 amount, OPEN/PENDING state, native approval observation and payee ID. The synthetic case must preserve that same ID, the USD 800 cap and USD 40 hypothetical difference, with no recovery, prevention or publishing authority. Changing the fixture requires reviewing the story, not choosing another convenient bill automatically.

The captured vendor list is truncated and does not contain this bill’s payee record. The film therefore shows the bill’s actual payee ID in its compact provider projection, without inventing a vendor name. A card transaction and available PO are separate observations, selected deterministically from the capture. Their money units are checked at runtime; neither is asserted to settle or govern the designated bill. Agreements and credits must remain explicitly EMPTY for this narration. These historical snapshot observations do not establish current provider balances or a complete portfolio.

The actual UI exposes **Inspect finding plan**, an authorized GET. The script checks `SIMULATION_ONLY` and `NOT_SENT` on the exact object. It does not call a provider comment API. There is no demonstrated native publish or Blank Canvas delivery action in this replay. A provider link is shown only when the API supplies it, checked against the rendered href, and never opened. The deeper dispute flow uses normal local buttons and simulated vendor outcomes. GENERAL onboarding uses `/#vendors` and the real signed `/api/vendors/{id}/candidates`, `/tests`, and `/shadow-preview` routes. The new candidate stays in SHADOW; no interpretation acceptance, approval, activation, dispatch or independent held-out evaluation is claimed.

UI text is literal application output. The separate caption band and the spoken script are authored editorial copy, not quoted provider statements. The band identifies the offline rehearsal and scripted test reviewer throughout. Sources marked `LIVE_RAMP_SANDBOX` identify the original capture; this filming session replays those observations offline. Synthetic customer terms and simulated vendor awards remain separate.

## Spoken script and timeline

Read at approximately 130 words per minute, leaving pauses for the evidence. Each paragraph corresponds to one scene; the encoder holds its screenshot for the stated interval.

| Time | View | Spoken copy |
|---|---|---|
| 0–8 | Ramp worklist | An approver starts with captured Ramp records. This is a historical sandbox replay, with incomplete coverage labelled. |
| 8–20 | Designated bill | This exact native bill is eight hundred forty dollars, OPEN, with approval PENDING. The capture contains no governing agreement or real credit. |
| 20–30 | Approval evidence | Open the record-bound evidence. Its approval observation carries a capture reference and digest. Contract enforcement requires verified rights and service evidence. |
| 30–37 | Payee | The bill supplies its payee ID. The truncated vendor list cannot supply a verified name here. |
| 37–44 | Card transaction | Card activity has its own native amount and status. It is separate spend, not recovered credit. |
| 44–54 | Purchase order | Available purchase-order details add procurement context. This separate PO does not establish governing terms for our bill. |
| 54–66 | Constructed cap | Now the same native ID meets constructed rehearsal terms: an eight-hundred-dollar gross cap. The forty-dollar difference is hypothetical, not saved money. |
| 66–78 | Informational plan | Inspect the informational note plan. It is simulation-only and not sent. Blank Canvas delivery is not demonstrated. No provider write occurs. |
| 78–86 | Synthetic dispute | Deeper disputes stay in Uptime. This synthetic Twilio claim requests one hundred dollars but still needs evidence. |
| 86–96 | Simulated award | The scripted reviewer approves a supplement. The vendor simulator awards one hundred dollars. An award is not yet a recorded or applied credit. |
| 96–103 | Recorded credit | Recording changes the simulated ledger stage. Applied remains zero. This is not a Ramp credit. |
| 103–110 | Partial application | Only fifty dollars is applied in replay. Disputed, awarded, recorded and applied remain distinct. |
| 110–120 | GENERAL onboarding | CalyxQuay’s recorded Opus extraction generates a new declarative draft. Editor-authored synthetic controls pass. Human interpretation and approval remain pending in SHADOW. |

## GENERAL onboarding provenance and controls

The only source is `prospective/public/calyxquay-beacon-cache-sla.txt`, authorized by `prospective/public-scope.json`. Its SHA-256 is `697b2b662246f6f08672cb23d59ca03cadfa506f117947ff12debd063e258cc1`. Root must copy the accepted artifact unchanged into `docs/v4/evidence/public-extractions/697b2b662246f6f08672cb23d59ca03cadfa506f117947ff12debd063e258cc1.json` before capture. The film refuses a missing artifact, changed source, or different model/session. It uses the existing opt-in proposition validator with `UPTIME_PUBLIC_EXTRACTIONS` pinned to that directory and `UPTIME_MODEL_PROPOSITIONS=1` only during capture.

The accepted extraction records model `claude-opus-5-5`, session `609751b5-43c2-4ddf-947d-799f6e5431ec`, timestamp `2026-11-05T01:59:33.188612+00:00` and proposal digest `7bff6902faf2bca6e52e4cf4e7b2c4bb1651e2dd9a38c574b4fb267d11be9a9f`. These are historical extraction observations. No model runs during the offline film. The final browser scene expands the actual candidate record and focuses its extraction provenance; the caption identifies SHADOW and human approval pending. `evidence.json` carries the exact extraction receipt, generated version and preview result.

The account, agreement alias, fee line, invoice, status record and filing receipt are **editor-authored synthetic demonstration data**, constructed from the public manifest and supported public schema. Their verification flags and content hashes describe simulated records, not real customer evidence. The controls independently specify the expected arithmetic: 60 unavailable minutes in 43,200; 12% of a $100 subscription = $12, excluding $50 of coaching. Filing exactly at the cutoff is permitted; one second late is ineligible; missing status evidence remains unknown. The application calls the submission form “Independent tests”; this demonstration is not an independent held-out success. No private holdout or original private gold was read to construct it. The public scope designates this source an in-family comparator only; prior evaluation limitations remain.

## Live refresh and deterministic film are separate modes

**Live refresh:** use the existing [operations runbook](OPERATIONS.md) and authenticated `scripts/ramp_refresh_workspace.py` importer in the operator’s sandbox workspace. That explicit operator command contacts Ramp and obtains new observations. Normal application entrypoints remain unchanged. A refresh does not grant commercial, comment, payment or claim authority. Do not use a refreshed workspace to narrate this historical film without rechecking its object bindings and rewriting the story.

**Deterministic film:** `film_ramp_v4.py` starts a disposable replay database, loads the committed historical capture and accepted extraction locally, and permits only loopback traffic. It performs no backend refresh and calls no provider or model. The exact historical $840 OPEN/PENDING bill, its constructed $800 cap and hypothetical $40 finding remain the same object throughout. Keep live-refresh credentials and logs outside film artifacts. Install dependencies before entering offline capture.

## Worker validation handoff

### Root verification after integration

Root rendered the complete film from commit `38bca3e` using the normal local application, authenticated browser interactions and the committed public extraction. All thirteen scenes were captured. Separate ffprobe verification reported H.264, yuv420p, 1280×900,120.000 seconds and2,880 frames. The final scene was visually inspected and shows CalyxQuay in SHADOW with the synthetic control results and source-kind labels. The source-linked extraction remains available in the same expanded record. The generated `evidence.json` records actual native identifiers, historical capture provenance and separate simulated ledger stages. This integrated result supersedes the earlier worker execution limits recorded below.

Worker results: all three film-specific tests passed using the installed engineering Python and the accepted artifact at the review location (temporary in-process path override, no artifact edits). The normal `uv run --locked pytest tests/test_film_ramp_v4.py -q` currently reports two passed and one failed because root’s repository artifact copy is pending. The actual `uv run --locked python scripts/film_ramp_v4.py --check` stopped with `PermissionError`; no capture was published. Rerun the film-specific tests and `--check` using the commands above after the accepted public artifact is copied. The signed HTTP test uses the actual application router with publishing disabled, verifies all three editorial controls, and rejects fabricated approval or activation. The browser check still needs a process permitted to bind loopback; a denied socket must be reported as a blocker, never replaced by mocked screenshots. Root owns rendering, visual inspection (especially the final provenance viewport), and ffprobe verification. Commit code, runbook and film tests only; keep large videos outside this change. Run `uv run --locked pytest` after each merge.
