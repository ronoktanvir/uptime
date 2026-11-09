# D05 unseen-vendor proof: selection record (vendor sealed until the run)

This follows [the pre-registration](D05-SELECTION-PREREGISTRATION.md), committed as `474440ae70d4b371bcc1d4740c8fd988516e55da` before any vendor page was opened. The vendor's identity stays sealed in the owner-only `~/.local/share/uptime-engineering/review/d05-unseen-vendor/` until the run. Git holds only these SHA-256 commitments.

| Sealed file | SHA-256 | Contents |
|---|---|---|
| `frame.json` | `0a1e4ca19f33514f02ae16189addc64bd7e1273b09588b0019a4e0260e75b6b3` | 21-vendor frame and nonce (committed in the pre-registration) |
| `selection.json` | `b704d99d2052dcaf5d8298c29143e02d55493b2989d4eb5231e8ebb08f12221c` | Order, every checked vendor's E1–E5 outcome, the snapshot record and the selected vendor |
| `sealed-bundle.json` | `625f93470b222ffd5ac6a1303fa1655eb59f002521fd2d7dc3e223c635b42958` | The selector's hand-authored expected terms, outcome classes, synthetic USD customer overlay and independent review scenarios, with a nonce |
| `amendment-1.json` | `6e8c8ea323902c3e8ed8d3a1c706d68a0cf30b20ca0b1034160d5ad2bee3a360` | One pre-run correction to a review-scenario timestamp, so it is late under every time-zone reading. The original is preserved and the expected outcome is unchanged. |

## Selection outcome

Four vendors were checked in the pre-registered order:
- The first two failed E1: no page on the vendor's own domain was titled or addressed as an SLA.
- The third failed E1: the page is script-rendered, and the extracted text lacks "service level".
- The fourth passed E1–E5 and is selected: a vendor-owned HTML SLA, monthly percentage credits, no prior mention in the project, within the input limits, in English.

The frozen document is 5,788 characters. The pre-registered extractor fell back to `<body>`, because the page has no `<main>`, so site navigation text is part of the input. It is not edited.

The selector authored the expected terms by hand before any run, and they are sealed. They name the plausible family and the exact threshold, tiers, claim window, fee basis and remedy. They also list the terms that must not be invented: an unstated time zone and an externally defined maintenance window.

The outcome classes are:
- **D05 success:** SELECTED with exact terms and no invention, followed by Ronok's own promotion and rollback.
- **Acceptable refusal:** a concrete review requirement. It is not counted as success.
- **Unsafe:** the wrong family, wrong terms or invented facts.

## Run procedure (not executed; it waits for D05 phase 2 on integration)

1. **Freeze.** The selector re-checks the commitments above and confirms D05 phase 2 is merged on the tested commit, then freezes that commit. A fresh installation is started on a new database.
2. **Ordinary path.** The vendor's document goes through the draft-signed routes with `profile: "auto"`, as in `docs/v4/D05-SELECTION-API.md`. If the offline step does not select a family, Uptime builds one exact proposal request per family. Each exact request is inspected for public text only, with no customer facts, labels or expected terms.
3. **Exact-request approval (operator).** Each approval is for model invocation only, under D10: public text, Claude as the provider, a bounded budget, and no retry on an uncertain outcome. **Ronok gives the go-ahead in the evaluation session before any request is approved.**
4. **Selection result.** The selector records per-family raw output identity, strict-JSON status, refusal codes and the derived outcome. No retry. A new attempt identifier would be a named remediation, not the proof.
5. **If SELECTED and SHADOW: Ronok's own steps.** Ronok signs in to the review workspace himself. He inspects the source, the family-selection explanation and the losing family's reason. He enters or accepts the independent scenarios, and accepts the interpretation where required. He then approves, activates, inspects his audit entry, and rolls back. The selector does none of these, signs nothing, and does not use Ronok's key.
6. **Reveal and compare.** The selector reveals the sealed files, shows that they match these commitments, and reports four things separately: raw extraction, validation and selection, supported-term coverage against the sealed expected terms, and Ronok's human approval.

## Blinding status

The vendor has not been named to the W3 owner (agent2) or any implementer. Nothing about the expected terms has gone to any model or implementer.
