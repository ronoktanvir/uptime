# D05 second attempt: selection record (vendor sealed until the run)

This follows [the second pre-registration](D05-SECOND-PREREGISTRATION.md), committed as `46feb9935f904c0ffe1de33dbbca97ffac223227` before any page was opened for this attempt. The sealed files are in the owner-only `~/.local/share/uptime-engineering/review/d05-unseen-vendor-2/`. Git holds only these commitments.

| Sealed file | SHA-256 |
|---|---|
| `frame.json` (20 vendors and a nonce; in the pre-registration) | `017af7a44e4688d94e8f0b70cccd2c9b41994499364f026c1382e686b03f1d32` |
| `selection.json` (order, each checked vendor's E1–E6 outcomes, snapshot record, chosen vendor) | `89c885631437ab4c4b9b5417dc8c4cba8388c40385399e7c02d9ce1fef0d1cb8` |
| `sealed-bundle.json` (hand-authored expected terms, ambiguities named in advance, outcome classes, synthetic USD overlay, review scenarios, nonce) | `409d6d9b7fc5fc29cb6bda6500c8b9efa24c0ecbfa49d44882c0e335424ce1e5` |

## Selection outcome

Two vendors were checked, in the pre-registered order.

The first failed E1: no result on its own domain was titled or addressed as an SLA.

The second passed E1–E6 and is selected:
- a vendor-owned HTML SLA;
- extractor v2 took the `<article>` region, 6,371 characters;
- monthly percentage credits;
- no whole-word mention on `origin/main`;
- within limits and in English;
- **E6 clean:** the text begins with the agreement's own purpose statement and ends with its remedy clause, with no navigation or footer chrome.

The expected terms name the plausible family and the exact credit mechanics, cap, claim window and evidence requirement. They also list what must not be invented and the ambiguities the source itself leaves open.

## Run

The run is **not executed**. It needs Ronok's separate go-ahead for at most 2 model calls. It uses the same driver and pre-call checks as attempt 1 (`work/d05-run-gent8`), on the newest integration head with a verified full suite at the time.

If the result is SELECTED and reaches SHADOW, promotion needs a path Ronok authorizes, because the current local review exception covers CalyxQuay only. The vendor has not been named to any implementer.
