# D05 unseen-vendor proof, second attempt: selection pre-registration

**Recorded before any vendor for this attempt was chosen, and before any candidate SLA page was opened for it.** Ronok asked for it ("Yes, pre-register", November 9, 2026). The selector is gent8, the evaluation lane.

Why there is a second attempt: run 1 (Backblaze) ended `NO_SUPPORTED_FAMILY`, a safe refusal whose correctness was not established. Its frozen input included the site's navigation text, and that confounded the result ([result](https://github.com/ronoktanvir/uptime/blob/work/release-evaluation-gent8/docs/v4/evaluation-gent8/D05-RESULT.md)). Run 1 stays as recorded and is never rescored.

## What changed from attempt 1, decided before choosing

1. **Boilerplate handling.**
   - The snapshot uses `scripts/d05_snapshot_v2_gent8.py`, SHA-256 `63dd4d7c9bcc568ea018354267531fcf831e47b34df72f5ad77c1571aaa8553b`, committed with this record.
   - **Content region:** the first `<main>`, otherwise `<article>`, otherwise an element with `role="main"`, otherwise `<body>`.
   - **Dropped:** script, style, noscript, svg, template, nav, header, footer, aside, form, button, dialog and iframe subtrees. Also any element whose id or class tokens include nav, navbar, navigation, menu, header, footer, cookie, banner, breadcrumb, sidebar, announcement, promo or skip.
   - **Normalization:** zero-width characters are removed.
   - Text is otherwise unedited, never trimmed by hand, and never truncated.
2. **New check E6 — clean page.**
   - The first extracted line must contain "service level", "SLA" or the vendor's name.
   - The last line must not contain ©, "copyright", "all rights reserved", "privacy" or "cookie".
   - A page that fails is not eligible. It is not trimmed.
3. **Frame.** Frame 1 minus the vendor already used: 20 vendors. Frame 1 was fixed before any page was opened in attempt 1 and was revealed after run 1. Reusing it prevents the selector from choosing new candidates with knowledge gained since.
   - The membership is therefore public. Which vendor is chosen stays sealed until the run.
   - Sealed file `~/.local/share/uptime-engineering/review/d05-unseen-vendor-2/frame.json`, SHA-256 `017af7a44e4688d94e8f0b70cccd2c9b41994499364f026c1382e686b03f1d32`. It holds the 20 names, a new nonce and frame 1's SHA-256.

## Selection order

Let `C` be the full SHA of the commit that adds this file. Each vendor gets the key `sha256("d05-selection/2:" + C + ":" + vendor)`, and vendors are checked in ascending key order.

## Eligibility checks

Checks run in order, for each vendor; the first vendor that passes all of them is selected. Every checked vendor's outcome is recorded.

1. **E1 — public SLA page.**
   - One web search, `<vendor> service level agreement`. Take the first result hosted on the vendor's own domain and titled or addressed as an SLA.
   - Snapshot it with extractor v2.
   - Pass requires HTTP 200, HTML (not PDF), and extracted text containing "service level".
2. **E2 — monthly percentage credit SLA.** The text contains "credit", "%" and "month".
3. **E3 — unseen.** `git grep -i -w <vendor>` on `origin/main` at check time finds no file.
4. **E4 — within limits:** at most 50,000 characters and an 80,000-byte document.
5. **E5 — English.**
6. **E6 — clean page**, as defined above.

If none of the 20 passes, the result is "no eligible vendor". The frame is not extended.

## Sealing, run and reporting

These follow [attempt 1's pre-registration](D05-SELECTION-PREREGISTRATION.md) unchanged:
- **Sealed before the run, with SHA-256 commitments in Git:** the selection record, snapshot, hand-authored expected terms, synthetic USD overlay and review scenarios.
- **The run:** the ordinary path with `profile: "auto"`, run only after Ronok gives a separate go-ahead for the model calls.
- **Human approval:** Ronok's own steps. Under the current release gate they need a promotion path he authorizes; no exception exists for a new vendor.
- **Reporting:** raw extraction, validation and selection, coverage and human approval, each reported separately.

The vendor is not named to the onboarding owner (agent2) or any implementer before the run.
