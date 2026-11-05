# Ramp-first two-minute demo

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

The actual UI exposes **Inspect finding plan**, an authorized GET. The script checks `SIMULATION_ONLY` and `NOT_SENT` on the exact object. It does not call a provider comment API. There is no demonstrated native publish or Blank Canvas delivery action in this replay. A provider link is shown only when the API supplies it, checked against the rendered href, and never opened. The deeper dispute flow uses normal local buttons and simulated vendor outcomes. Onboarding stays in SHADOW; no unseen deployment or independent evaluation claim is made.

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
| 110–120 | Shadow onboarding | Onboarding remains in shadow with visible checks. Reviewer actions were scripted locally. No actual customer recovery or external deployment is shown. |

## Worker validation handoff

The data/timeline boundary test passes against the committed capture, including refusal of a changed native ID, amount, publishability or recovery assertion. This worker’s `--check` attempt stopped with `PermissionError`; no capture was published. Browser actions, screenshot composition and the final encode still require root execution. Missing UI capabilities to report: native publish/Blank Canvas delivery is not available in this replay; the exact payee’s full vendor record is absent from the truncated capture. Neither is substituted with fabricated content.
