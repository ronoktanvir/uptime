# Two-minute offline walkthrough

The walkthrough runs the actual web application on a fresh SQLite database. Playwright opens a new headless Chrome process, authenticates in memory as `scripted-test-reviewer`, reads the offered actions, and clicks the corresponding visible controls. It captures 17 browser frames after the server confirms the state changes. FFmpeg holds each frame for its scripted duration and burns captions into a band beneath the viewport. This is a timed, silent walkthrough of captured UI states.

Run these two commands from the assembled repository on macOS. They require the locked project dependencies, system Google Chrome, FFmpeg with libass and libx264, and ffprobe. Choose a new or empty output directory for each capture.

```sh
uv run --locked python scripts/film_demo.py --output /tmp/uptime-demo-film
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,pix_fmt,duration,nb_frames -of json /tmp/uptime-demo-film/walkthrough.mp4
```

The expected result is **120.000 seconds**, 2,880 frames, H.264 `yuv420p` at 1280 × 900. The output includes five captioned stills and a scene manifest. Recording and playback require no provider account. Routine application timestamps change between captures.

| Playback | Evidence on screen |
|---|---|
| 0:00–0:22 | Ledger exposure and the amended usage line. The $27,500 charge prices to $20,000; $7,500 is flagged on an unpaid synthetic invoice. |
| 0:22–0:36 | A qualifying Twilio case with $100 in candidate credit, followed by refusal of an excluded maintenance interval. |
| 0:36–1:11 | Missing component evidence is cured, a corroborated denial is accepted, and unresolved maintenance notice goes to human review. |
| 1:11–1:25 | A $100 simulated award is recorded and $50 is applied to a simulated bill. |
| 1:25–1:51 | Atlassian passes shadow checks. Scripted approval, local activation and rollback run against the disposable database. |
| 1:51–2:00 | The finance ledger distinguishes modeled outcomes from the separately captured Ramp sandbox read capability. |

The browser opens only the loopback rehearsal server. The login URL never appears on a page or in output. The database, credentials and transient raw frames are discarded after encoding. The film never reads the operator’s normal browser profile, sandbox credentials or application database.
