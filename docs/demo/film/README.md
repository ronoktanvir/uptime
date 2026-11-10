# The demo film

[`uptime-demo.mp4`](uptime-demo.mp4?raw=true) is 2:47.8 long, 1920×1080, narrated, with no captions. GitHub does not play video files in place, so the link downloads it (10 MB). It was made on November 10, 2026 from this repository's code. [`narration.md`](narration.md) has every spoken line with its times.

`walkthrough.mp4` and the stills beside it are the earlier silent cut, kept for the record. They show the interface as it was before the redesign.

## What is captured live, what is composited, what is synthesized

**Captured live from the running app, in real time**

- Every frame of the Uptime scenes: the case page, the portfolio, the template builder, the four reviewer decisions and the close. They are Chrome's own screencast of the app. Nothing is sped up, slowed down or reordered inside a scene.
- Every click in those scenes is a real click, and what follows is the app's real response at its real speed.
- The template builder scene is one real run, shown whole (22.6 seconds from the click to "Ready for a reviewer"): a real Jev decision, three real Claude readings in parallel, a real Claude-written template, the app's own checks, real Jev checks per term, an approval by the scripted reviewer account, and a real read of the next contract by the template.
- The side panel's contents: the extension's own page, unchanged, framing the running app's page for each Ramp bill.

**Composited (the Ramp scenes)**

- **The browser window is drawn.** The tab strip, the address bar, the toolbar button with its badge and the side panel's frame are a drawn stage. It is not a screen recording of Chrome.
- **The two halves of that window are separate real captures.** The left half is a still of a real page in Ramp's sandbox. The right half is the live panel. They were not on one screen together when captured.
- The Ramp pages are stills: nothing in them is clicked, typed or scrolled. Moving from one Ramp page to another is a cut between two stills behind a drawn pointer.
- To run outside Chrome's side panel, the extension's page was given a stand-in that answers "which tab is active", and the capture browser let the stage frame the app. Neither the app's code nor the extension's was changed.

**Added in the edit**

- The pointer, its trail, the ring at each click and the highlight that dims everything but one thing.
- Cuts between scenes. There are no dissolves, captions, titles or music.

**Synthesized**

- The narration is a built-in synthetic voice (macOS `say`, "Daniel"). It is a stand-in for a recorded voice.

## What the film must not be taken to show

- **No credit was applied in Ramp, and no Ramp balance changed.** The $8,600.00 is the April invoice's balance in Uptime only. The vendor credit on Ramp's "Vendor credit" page was entered by hand in Ramp's sandbox; Uptime did not create it, and Ramp shows it as "Not applied".
- The vendor is a simulated counterparty and the contracts are authored samples. The narration says so in the claim scene.
- The reviewer is the scripted test account `scripted-test-reviewer`, not a person.
- Uptime's notes on the bills are real records in Ramp's sandbox, posted through Ramp's API by the app.
- "Agent" in the narration means Claude only. The steps the case page tags "Uptime · automatic" are fixed rules.

## Scene by scene

| Starts | Length | Kind | What it shows |
|---:|---:|:---|:---|
| 0:00 | 14.5 s | stage | Ramp: the Bills list, the Northwind bill, its Activity with Uptime's note |
| 0:14 | 13.2 s | stage | The panel opens beside the bill: the credit, the clause, the inputs |
| 0:27 | 15.8 s | stage | Three other bills: March's price exception, Corvid's estimate, a bill with no agreement |
| 0:43 | 2.3 s | stage | The panel's button is pressed |
| 0:45 | 9.4 s | app, live | The case page, then the portfolio |
| 0:55 | 48.1 s | app, live | A new contract type: Jev, three Claude readers, the template, checks, approval, the next contract by fixed rules |
| 1:43 | 42.3 s | app, live | The claim: four reviewer decisions and the steps between them |
| 2:25 | 15.0 s | stage | Back in Ramp: the bill's Activity with both notes, then the vendor credit page |
| 2:40 | 7.1 s | app, live | The portfolio, to close |

## The template builder run in the film

Read from the page during the take:

- Jev: "No template on file matches", done in 0.2 s (`jev-1.13.0`).
- Three Claude readers, 9 terms and 9 quotes each; the template builder wrote 9 extraction rules.
- Every quote is in the contract, word for word: 27 of 27.
- The three readers agree: 9 of 9.
- The template returns every term from this contract: 9 of 9.
- The template reads a second contract of the same form: 9 of 9.
- Jev, each term is supported by its sentence: 8 of 9, lowest 85% against a threshold of 90%; that term was marked for the reviewer.
- Approved by `scripted-test-reviewer`. Then the next contract: read by fixed rules, 0 model calls, 0.9 ms, 9 of 9 terms.

## Things a viewer may notice

1. **Two counts of automatic work.** The narration says "seven steps ran on their own", which is the case page's own line (Uptime's own steps plus events received from the vendor and other sources). The portfolio's counter "Uptime · automatic" shows 2, because it counts only Uptime's own steps.
2. **Two company names.** Ramp's sandbox business is "Save Time Inc"; the Uptime workspace is named "Harborline Analytics".
3. **Dates in Ramp.** The Northwind and Corvid bills were entered in Ramp's sandbox on November 10, 2026, so Ramp's list shows that date under each vendor, while their invoice dates are earlier.

## How it was checked

Eighteen measured checks passed on this cut: format and length, that every narration line fits its scene, loudness, and that the page really showed what the narration says (the $8,600.00 balance, 4 reviewer decisions and 7 automatic steps, Jev's decision, the read with no model call, the approval by the scripted account). An AI agent looked at frames across the film. It cannot hear, so the narration has not been listened to against the picture by the agent that made it.
