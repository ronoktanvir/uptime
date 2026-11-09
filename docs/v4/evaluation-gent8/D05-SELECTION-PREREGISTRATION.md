# D05 unseen-vendor proof: selection pre-registration

**Recorded before any vendor was chosen and before any candidate SLA page was opened in this session.** The selector is gent8, the independent evaluation lane. The overview session assigned this task under Ronok's delegated (Recommended) authority on November 9, 2026. It is not Ronok's personal decision.

The purpose is the proof decision D05 requires: automatic family selection among supported families, then a person's approval, on an independently selected unseen vendor through the ordinary application path.

## Blinding

The W3 onboarding owner (agent2) and other implementers must not learn the vendor before the run. Three things are therefore sealed outside Git, in the owner-only directory `~/.local/share/uptime-engineering/review/d05-unseen-vendor/`:
- the candidate frame;
- the chosen vendor;
- its snapshot.

Git carries only SHA-256 commitments until the run. After the run, everything is revealed and checked against these commitments.

- **Candidate frame:** sealed file `frame.json`, SHA-256 `0a1e4ca19f33514f02ae16189addc64bd7e1273b09588b0019a4e0260e75b6b3`. It holds 21 well-known SaaS and cloud vendors that the selector believed publish online SLAs, plus a random nonce. The selector fixed it from general knowledge, without opening any page. That knowledge is the main residual bias; the rest of the procedure is mechanical so the selector cannot pick by phrasing.

## Selection order

This pre-registration is committed and pushed first. Let `C` be the full SHA of that commit. Each frame vendor gets the key `sha256("d05-selection/1:" + C + ":" + vendor)`. Vendors are checked in ascending key order. `C` cannot be known before the commit exists.

## Eligibility checks

Checks run in order, for each vendor. The first vendor that passes all of them is selected. Every checked vendor's outcome is recorded; none is skipped.

1. **E1 — public SLA page.**
   - One web search, `<vendor> service level agreement`. Take the first result that is hosted on the vendor's own domain and titled or addressed as an SLA.
   - Snapshot it with `scripts/d05_snapshot_gent8.py` (committed with this pre-registration; SHA-256 `86e56f5a0c9696fa99782f72f995ed3259b561d85d77e41be512a764850b17e9`).
   - Pass requires HTTP 200, HTML (not PDF), and extracted text containing "service level" (case-insensitive). The last condition excludes login walls and script-only pages.
2. **E2 — monthly percentage credit SLA.** The extracted text contains "credit", "%" and "month", case-insensitive. The selector does not judge whether Uptime will parse it.
3. **E3 — unseen.** At check time, `git grep -i -w <vendor>` finds no file on `work/integration-90`, nor on the D05 implementation branch head. The vendor is not a corpus84 vendor.
4. **E4 — within the application's input limits:** at most 50,000 characters of text and an 80,000-byte document. No truncation or editing.
5. **E5 — English** text.

If no vendor passes, the proof is reported as "no eligible vendor in the frame". The frame is not extended.

## Before the run (sealed, with commitments in Git)

1. **Selection record:** every checked vendor with its E1–E5 outcomes and the chosen vendor. Commit the SHA-256 only.
2. **Snapshot:** raw page bytes and the extracted `document.json`. Commit the SHA-256 values only.
3. **Independent expected terms**, authored by the selector from the snapshot by hand: the expected family (`monthly-propositions`, `resource-month`, or no supported family), and if supported, the threshold and credit table, measurement period and claim window. This is the oracle for coverage. Commit the SHA-256 only. Nothing about the expected terms goes to any implementer or model.
4. **Synthetic customer overlay**, authored after reading the plan names: fictional account and agreement, USD, calendar months, per D07. Kept sealed with the snapshot.

## The run

The run happens after D05 phase 2 is merged. It goes through the ordinary app path, with `profile: "auto"` on draft-signed routes. Each required exact proposal request is approved by its operator under D10: public text only, Claude as the provider, a bounded budget, and no retry on an uncertain outcome.

Promotion and rollback are done by Ronok personally in the browser. The selector prepares the steps but does nothing in his name: no approval, activation, rollback or signature.

## Reported separately

- **Raw extraction:** per-family provider output identity, and whether output was strict JSON.
- **Validation:** per-family refusal codes, and the selection outcome (`SELECTED`, `AMBIGUOUS`, `NO_SUPPORTED_FAMILY` or `INCOMPLETE`).
- **Supported coverage:** extracted terms compared with the sealed expected terms.
- **Human approval:** Ronok's own actions, kept distinct from any scripted record.

One vendor is one sample. It is not a generalization estimate. A failure is reported as observed; any later repair is a named remediation, never a replacement score.
