# Template builder: real public service-level agreements

A judge wrote that the template builder "has not read a contract it wasn't written for". The held-out evaluation
(`TEMPLATE-BUILDER-HELDOUT.md`) used contracts written by other Claude calls. This page is the first time real vendor
SLAs went through it: 13 public SLA pages from 11 vendors, one build each, on November 11, 2026 (UTC), with the
version 3 engine (commit `1fa66d2`: a credit schedule of one to six tiers, durations in the contract's own unit).
Nothing in the engine, its prompts or its thresholds was changed after seeing these pages. The result is published as
it came out.

**Later tables.** After this run the choice terms' check was changed (version 3.1). The second table below measures
it on 13 fresh pages from vendors not used here, keyed before the builder ran; the third table is a re-run of these
13 pages on the fixed engine, which is not a clean number. The first table and its sections are left as they were.

**Headline (first run).** One of 13 pages (MongoDB Atlas) produced a template that passed every blocking check; the script
approved it and its guarded read returned 4 correct values, 0 wrong, 1 not read and 2 not stated. The other 12 were
stopped before approval: 11 at a blocking check, 1 because the template builder's answer had the wrong shape. **No wrong
value was returned downstream, and none was shown to the reviewer** (after one correction to my key, below). Most of
the refusals come from one fixed code check, `value_in_sentence`, on the two choice terms; see "Why most builds were
refused".

## How the pages were chosen and fetched

- **Chosen** from memory of where vendors publish their SLAs, across cloud compute and storage (AWS EC2 and S3, Google
  Compute Engine and Cloud Storage, DigitalOcean Droplets, Backblaze B2), database (MongoDB Atlas), communications APIs
  (Twilio, Mailgun), developer tools (GitHub, Vercel), SaaS collaboration (Atlassian) and network (Cloudflare Business),
  preferring the vendor's own legal page. Three first guesses answered 404 (DigitalOcean `/legal/sla`, MongoDB
  `/legal/sla/atlas`) or were an index (Twilio's SLA list) and were replaced once, by a web search's result for the
  first two and by the index's own link for Twilio. Linode and Zendesk answered 404 and were not replaced; Slack's page is
  drawn by script (771 characters of text) and was not built. Those three are recorded in `sources.json`.
- **Fetched** by `scripts/evaluate_public_slas.py --fetch`: one plain HTTPS GET per page with `urllib` (generic
  User-Agent), the bytes and text cached under `~/uptime-demo/public-slas/`, outside the repository; later runs use the
  cache. HTML becomes text with `html.parser`: scripts, styles, navigation and footers dropped, block elements end a
  line, a table row is one line with cells joined by " | ". The page's site navigation and other boilerplate stay in.
- **The 60,000-character limit.** No page was over it (the longest, Google Cloud Storage, is 43,626 characters), so no
  page was cut and none was recorded as too long. The script's stated rule (cut from a start line to an end line given
  per source) was not used.
- `fixtures/template_builder_public/sources.json`: URL, retrieval time, HTTP status, byte count, SHA-256 of the bytes
  and of the text, and the cut (none).

## How each page was built and scored

- One build per page, one at a time, through `TemplateBuilds.start` as a pasted contract with **no second contract**
  (so the second-contract check did not run), with the real Claude Code CLI and real Jev (`JevClient`, which reads its
  own key file). A build whose blocking checks all passed was approved by the script as `evaluation-script`
  (acknowledging exactly the flagged terms; a script, not a person) and the same text read by the approved template
  through the guarded read.
- **The key** (`fixtures/template_builder_public/key.json`, values only) was written by me, the evaluating agent
  (Claude Opus 5.5), by reading each cached page, after I had seen the builder's term list. Where a page states several
  commitments (per service, plan or storage class), the key takes the first one listed and lists the others under
  `other_service`; a value matching one of those would be scored "other service", not correct (it never happened).
  Vercel's tiers are ranges with inclusive upper ends; the key accepts either the upper end (99.98%) or the commitment
  (99.99%) as the first threshold. Choices I made that cost the builder: AWS S3's and MongoDB's commitment, stated only
  by the tables, is keyed as the top threshold; "by the end of the second billing cycle" (AWS), "within two billing
  cycles" (DigitalOcean), "by the end of the month following" (MongoDB, Cloudflare) are keyed as 2 or 1 months; Google
  Compute's cap ("not exceed the amount due") is keyed as 100%. Another reader could key these as not stated.
- **One key correction after the run.** I had keyed Twilio's maintenance notice as not stated. The builder showed
  24 hours; its sentence is in Twilio's exclusions, which I had missed. The builder was right; the key now says 24
  hours, with a note. Before the correction this was the only "wrong" value, shown to the reviewer on a build that was
  refused anyway.
- **Two views are scored, per term** (correct; wrong, a value returned that is not the key's; not read; not stated, the
  key says the page does not state it and nothing was returned): **returned downstream** (the accepted guarded read; a
  refused build or read returns nothing) and **shown to the reviewer** (the readers' agreed values on the build page,
  whether or not it could be approved).

## The table, as the script printed it

```
uv run --locked python scripts/evaluate_public_slas.py --score fixtures/template_builder_public/results/20261111T015844Z.json
                                                                   returned downstream (accepted read) | shown to the reviewer
page           build                  refused at                     ok wrong unread  n/s other |   ok wrong unread  n/s other   secs claude  jev
-------------------------------------------------------------------------------------------------------------------------------------------------
aws-ec2        READY_FOR_REVIEW       value_in_sentence               0     0      5    2     0 |    4     0      1    2     0   39.7      4    6
aws-s3         READY_FOR_REVIEW       stated,quotes,value_in_sente    0     0      5    2     0 |    3     0      2    2     0   32.5      4    5
gcp-compute    READY_FOR_REVIEW       value_in_sentence               0     0      6    1     0 |    5     0      1    1     0   71.8      5    7
gcp-storage    READY_FOR_REVIEW       value_in_sentence               0     0      6    1     0 |    6     0      0    1     0   50.9      4    8
digitalocean   READY_FOR_REVIEW       value_in_sentence               0     0      5    2     0 |    4     0      1    2     0   15.8      4    4
linode         not built: HTTP 404
backblaze      READY_FOR_REVIEW       value_in_sentence               0     0      5    2     0 |    5     0      0    2     0   27.2      4    6
mongodb-atlas  approved, read ACCEPTE -                               4     0      1    2     0 |    4     0      1    2     0   28.0      5    7
twilio         READY_FOR_REVIEW       quotes,value_in_sentence        0     0      6    1     0 |    6     0      0    1     0   34.4      4    6
mailgun        READY_FOR_REVIEW       stated,value_in_sentence        0     0      4    3     0 |    4     0      0    3     0   21.0      4    4
github         READY_FOR_REVIEW       value_in_sentence,reproduce     0     0      5    2     0 |    5     0      0    2     0   52.7      6    7
vercel         READY_FOR_REVIEW       value_in_sentence               0     0      6    1     0 |    6     0      0    1     0   29.7      4    8
atlassian      FAILED                 -                               0     0      5    2     0 |    0     0      5    2     0   48.8      4    0
slack          not built: only 771 characters of text (the page is probably drawn by script)
zendesk        not built: HTTP 404
cloudflare     READY_FOR_REVIEW       stated,value_in_sentence,rep    0     0      3    4     0 |    1     0      2    4     0   48.8      6    1

returned downstream: 4 correct, 0 wrong, 62 not read, 25 not stated, 0 another service's value
shown to the reviewer: 53 correct, 0 wrong, 13 not read, 25 not stated, 0 another service's value
```

"build" is the build's state; a READY_FOR_REVIEW build with a check under "refused at" could not be approved.
58 Claude calls and 69 Jev calls in 501.3 seconds of builds. Every page has 7 terms; 13 pages, 91 terms in each view.

## Wrong values

**None in either view** after the key correction above. Before it: one, shown to the reviewer (Twilio,
`maintenance_notice`: key not stated, shown 24 hours), which was my key's error.

## Why most builds were refused

| Page | Blocking checks that failed | Cause |
|:---|:---|:---|
| AWS EC2 | value_in_sentence (2 of 4) | Measurement period "monthly billing cycle": the check wants the word "month"; credit "against future payments": the check wants the word "invoice" |
| AWS S3 | stated, quotes (12 of 13), value_in_sentence | Every reader said the commitment is not stated as a number (it is only in the tables); one reader quote not in the text; same two choice words |
| Google Compute | value_in_sentence (4 of 5) | Credit "credited to Customer's future monthly bills": no word "invoice" |
| Google Storage | value_in_sentence (5 of 6) | Credit "applied to future use": no word "invoice" |
| DigitalOcean | value_in_sentence (3 of 4) | Credit "credited towards future invoices": the check's pattern is the singular word "invoice", so the plural fails. **A defect in the check**, found by this run and left unfixed so these numbers stand |
| Backblaze | value_in_sentence (4 of 5) | Credit "applied ... against the Customer's next payment": no word "invoice" |
| MongoDB Atlas | none | Approved by the script; read ACCEPTED |
| Twilio | quotes (17 of 18), value_in_sentence (5 of 6) | One reader quote not in the text; credit "applied to future amounts payable": no word "invoice" |
| Mailgun | stated, value_in_sentence | The credit is a rate (a percentage per 30 minutes of downtime), not tiers, so the schedule is not stated; "monthly billing period" fails the "month" word |
| GitHub | value_in_sentence, reproduce (5 of 6) | The payment term ("a refund or a credit to Customer's account"): two readers said not stated, one said refund, so the term stayed stated with no value |
| Vercel | value_in_sentence (4 of 6) | Its tier table is not an HTML table: each range and each credit is a separate line, so no tier's sentence holds its credit; "future monthly fees": no word "invoice" |
| Atlassian | (build failed) | The template builder's map for the measurement period was not phrase to option; the build stops on a wrong-shaped first answer |
| Cloudflare | stated, value_in_sentence, reproduce | A 100% commitment with a formula credit (outage minutes times the share of affected visitors), not tiers; rules for two terms read nothing |

The two choice terms' "value in its sentence" words (`CHOICE_WORDS` in `uptime/template_rules.py`: "month",
"quarter", "year", "invoice", "refund", "balance") were written for the authored samples. Real SLAs say "monthly
billing cycle", "future payments", "future monthly bills", "next payment", "future invoices". The values the readers
gave were correct in every one of these cases (they are counted correct in "shown to the reviewer"); the check refused
them. I did not change the word list or the plural defect, because this evaluation must not tune the engine to its
own score; that is the obvious next change, and a fresh set of pages would be needed to measure it.

## What the builder cannot express at all (current: all 26 pages)

Counted from the two keys (each written by reading the page), over the 13 first pages and the 13 fresh ones. These
are the shapes the term set has no place for; they are recorded as not stated (or lost), never guessed.

| Limit | First 13 | Fresh 13 | Pages |
|:---|--:|--:|:---|
| Several commitments in one document (per service, region, storage class, plan or deployment); a template has one commitment and one schedule, and every build took the first listed | 6 | 4 | AWS EC2, AWS S3, Google Compute, Google Storage, Atlassian, Twilio; Virtua, Shockbyte, OneUptime, Aerospike |
| Credits as a rate, formula or service time, not percentage tiers | 2 | 3 | Mailgun, Cloudflare; Virtua (hours of service), Shockbyte (day for day), Ably (formula) |
| No service credits at all (support levels only, or availability without credits) | 0 | 2 | Sinch, Plivo |
| Claim deadlines as calendar points or billing cycles ("by the end of the month following", "within two billing cycles"), keyed as months but read by nobody | 5 | 3 | AWS EC2, AWS S3, DigitalOcean, MongoDB, Cloudflare; Neon, Upstash, ClickHouse |
| Caps in other units (days of service, a month of fees per year, a share of fees over a longer period) | 2 | 1 | GitHub, Cloudflare; Supabase |
| A commitment stated only through the credit table | 2 | 3 | AWS S3, MongoDB; Neon, ClickHouse, Upstash |
| A payment term with two outcomes, or worded both ways | 1 | 1 | GitHub; Supabase ("credit to Customer's account", "applied to future billing charges") |
| Tier tables whose cells are not one line each | 1 | 0 | Vercel |
| Pages drawn by script (no text without a browser) | 1 | 1 | Slack; Wasabi |

**Where a claim window starts is not a term.** \`claim_window\` holds a number and a unit and nothing else. Pages
start the count from different points: Civo gives 30 days "from the date of an outage"; OneUptime gives 30 days "of the
incident" in its summary and 30 days from the end of the month in its claim section; the shipped sample counts from the
end of the month. The money link counts every window as calendar days after the end of the month, so for a page like
Civo's it would give a later deadline than the page states. No estimate or claim was run on a real page, so this
produced nothing wrong here, but it is a limit of what a template holds. Scoring a claim window "correct" in these
tables means the number and unit match the key; the starting point is not keyed or scored.

Also, from the held-out forms: tiers stated through defined terms ("Tier Threshold", "Tier 1 Credit").

## After the phrase fix: fresh pages (second table)

**The fix was made after seeing the first table.** It replaces the choice terms' word list with the contract's own
phrase (`docs/demo/TEMPLATE-BUILDER.md`, "Version 3.1"; commit `46d1968`). **These pages were not seen when it was
made.** Vendors: none of the first thirteen (nor Linode, Zendesk or Slack), chosen by a web search for each vendor's own
SLA page, fetched once with the same plain GET (Vultr failed on a TLS certificate error and Wasabi's page is drawn by
script, so 13 of 15 were built). Their key (`key_fresh.json`) was written after reading each page and **before any
build ran on it**, at 2026-11-11T02:17:13Z, and committed (`20e68f6`) before the run started at 02:17:19Z. One key
value was changed after the run and is recorded in the key's `_changes`: Neon's maintenance notice, which I had keyed
not stated; the page's definition of unscheduled downtime excludes maintenance disclosed with at least 24 hours'
notice. The builder showed 24 hours, which was right. Engine `20e68f6` (the fix plus the evaluation script; no engine
change after the fix).

```
uv run --locked python scripts/evaluate_public_slas.py --set fresh --score fixtures/template_builder_public/results/fresh-20261111T021719Z.json
                                                                   returned downstream (accepted read) | shown to the reviewer
page           build                  refused at                     ok wrong unread  n/s other |   ok wrong unread  n/s other   secs claude  jev
-------------------------------------------------------------------------------------------------------------------------------------------------
vultr          not built: URLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)
civo           approved, read ACCEPTE -                               7     0      0    0     0 |    7     0      0    0     0   24.8      4   10
virtua         READY_FOR_REVIEW       stated                          0     0      1    6     0 |    1     0      0    6     0   13.7      4    1
shockbyte      READY_FOR_REVIEW       stated                          0     0      4    3     0 |    4     0      0    3     0   17.2      4    4
wasabi         not built: only 316 characters of text (the page is probably drawn by script)
ably           READY_FOR_REVIEW       stated,value_in_sentence,rep    0     0      5    2     0 |    4     0      1    2     0   45.2      6    4
sinch          READY_FOR_REVIEW       stated                          0     0      3    4     0 |    3     0      0    4     0   25.7      5    3
plivo          FAILED                 -                               0     0      0    7     0 |    0     0      0    7     0    7.6      3    0
gitlab         FAILED                 -                               0     0      5    2     0 |    0     0      5    2     0   29.0      4    0
oneuptime      approved, read ACCEPTE -                               7     0      0    0     0 |    7     0      0    0     0   35.7      4   10
supabase       approved, read REFUSED read guards: template_match     0     0      5    2     0 |    4     1      0    2     0   27.1      4    9
neon           READY_FOR_REVIEW       value_in_sentence,reproduce     0     0      6    1     0 |    5     0      1    1     0   62.0      6    8
upstash        approved, read ACCEPTE -                               4     0      1    2     0 |    4     0      1    2     0  103.1      4    7
clickhouse     READY_FOR_REVIEW       stated                          0     0      6    1     0 |    4     0      2    1     0  110.6      4    6
aerospike      READY_FOR_REVIEW       stated,value_in_sentence,rep    0     0      6    1     0 |    4     0      2    1     0  135.3      6    4

returned downstream: 18 correct, 0 wrong, 42 not read, 31 not stated, 0 another service's value
shown to the reviewer: 47 correct, 1 wrong, 12 not read, 31 not stated, 0 another service's value
WRONG (shown) supabase credit_application: key "next_invoice", shown "account_balance"
```

58 Claude calls and 66 Jev calls, 637.0 seconds of builds.

**The reader prompt's examples were real wording.** When this table was run, the reader prompt gave three example
choice phrases. Two were AWS's wording from the first set: "monthly billing cycle" (in the cached text of AWS EC2, AWS
S3, DigitalOcean and Upstash) and "against future payments" (in AWS EC2, AWS S3, Ably, Neon and Upstash); the third,
"credited to your next invoice", is in none of the pages. So on three fresh pages (Ably, Neon, Upstash) an example
in the prompt was literally the answer phrase, and Upstash is one of the pages that passed. The coordinator found
this and replaced the examples with invented phrases (integration commit `08dd0b7`); the next table re-runs these pages
on that prompt.

- **Approved and read:** Civo (7 of 7 correct), OneUptime (7 of 7), Upstash (4 correct; the claim window, "before the
  end of the second billing cycle", was read by nobody). Supabase's template was approved, but its read of the same
  page was **refused by Jev's template-match guard** (Jev answered "unrecognised" at 0.66 for the page the template was
  built from).
- **Refused at `stated`** because the page has no percentage tiers (Virtua, Shockbyte, Ably, Sinch), or states the
  commitment only through tables or per deployment (ClickHouse, Aerospike). These are refusals of what the term set
  cannot express, not misreadings.
- **Neon:** `value_in_sentence` and `reproduce` failed on the claim window, where readers split on whether "by the end of
  the month following" is stated.
- **Build failures:** Plivo (every reader said nothing is stated: the page is about support levels); GitLab (the
  template builder's choice map came back in the wrong shape, the same failure Atlassian had in the first run).

**Wrong values, one by one:** returned downstream: none. Shown to the reviewer: one. Supabase, `credit_application`: key
`next_invoice`, shown `account_balance`, from the phrase "issue a credit to Customer's account"; the page also says the
credits "may only be applied to future billing charges". My key chose the latter; two of three readers chose the former.
The build could not reach a downstream value for this page anyway (its read was refused).

## Re-run of the first thirteen on the fixed engine (third table)

**This is a re-run on the pages the fix was made from, not a clean number.** Same pages (the cached text, not
re-fetched), same key (`key.json`, with the Twilio correction made after the first run), engine `20e68f6`.

```
uv run --locked python scripts/evaluate_public_slas.py --set first --score fixtures/template_builder_public/results/20261111T022756Z.json
                                                                   returned downstream (accepted read) | shown to the reviewer
page           build                  refused at                     ok wrong unread  n/s other |   ok wrong unread  n/s other   secs claude  jev
-------------------------------------------------------------------------------------------------------------------------------------------------
aws-ec2        approved, read ACCEPTE -                               4     0      1    2     0 |    4     0      1    2     0   32.1      4    7
aws-s3         FAILED                 -                               0     0      5    2     0 |    0     0      5    2     0   90.0      3    0
gcp-compute    FAILED                 -                               0     0      6    1     0 |    0     0      6    1     0   90.0      3    0
gcp-storage    approved, read ACCEPTE -                               6     0      0    1     0 |    6     0      0    1     0  118.2      4    9
digitalocean   approved, read ACCEPTE -                               4     0      1    2     0 |    4     0      1    2     0   16.1      4    5
linode         not built: HTTP 404
backblaze      FAILED                 -                               0     0      5    2     0 |    0     0      5    2     0   23.3      4    0
mongodb-atlas  approved, read ACCEPTE -                               4     0      1    2     0 |    4     0      1    2     0   22.1      4    7
twilio         READY_FOR_REVIEW       quotes                          0     0      6    1     0 |    6     0      0    1     0   32.5      4    6
mailgun        READY_FOR_REVIEW       stated                          0     0      4    3     0 |    4     0      0    3     0   18.6      4    4
github         approved, read ACCEPTE -                               5     0      0    2     0 |    5     0      0    2     0   25.3      4    8
vercel         READY_FOR_REVIEW       value_in_sentence               0     0      6    1     0 |    6     0      0    1     0   26.9      4    8
atlassian      READY_FOR_REVIEW       stated,value_in_sentence,rep    0     0      5    2     0 |    3     0      2    2     0  101.2      6    3
slack          not built: only 771 characters of text (the page is probably drawn by script)
zendesk        not built: HTTP 404
cloudflare     READY_FOR_REVIEW       stated,value_in_sentence,rep    0     0      3    4     0 |    2     0      1    4     0   45.3      6    2

returned downstream: 23 correct, 0 wrong, 43 not read, 25 not stated, 0 another service's value
shown to the reviewer: 44 correct, 0 wrong, 22 not read, 25 not stated, 0 another service's value
```

54 Claude calls and 59 Jev calls, 641.6 seconds of builds.

- Five templates were approved and their reads accepted (first run: one): AWS EC2, Google Storage, DigitalOcean,
  MongoDB and GitHub; 23 terms were returned correct with 0 wrong (first run: 4 correct).
- **Four builds failed for reasons unrelated to the fix**, and are counted as not read: AWS S3 and Google Compute,
  because two or three readers did not answer within 90 seconds (the first run's readers did, on the same text);
  Backblaze, because the builder's answer did not have one rule per term; Atlassian built this time but was refused at
  `stated` (its two plans give two commitments).
- No wrong value in either view.

The first table above is unchanged, as the record of the engine before the fix.

## The same fresh pages again, with only the prompt's examples replaced (fourth table)

**These are the same 13 fresh pages, seen once already, run again with only the reader prompt's three example
phrases replaced by invented ones** ("in any one calendar quarter", "returned to you as a refund", "kept as a balance on
your account", which are in none of the 26 pages or the repository's contracts). It checks whether the first fresh
result leaned on those examples; **it is not a new clean measurement.** Same cached text, same `key_fresh.json` (with
its one recorded change), engine `08dd0b7`; nothing else in the engine, prompt, checks or thresholds changed.

```
uv run --locked python scripts/evaluate_public_slas.py --set fresh --score fixtures/template_builder_public/results/fresh-20261111T043341Z.json
                                                                   returned downstream (accepted read) | shown to the reviewer
page           build                  refused at                     ok wrong unread  n/s other |   ok wrong unread  n/s other   secs claude  jev
-------------------------------------------------------------------------------------------------------------------------------------------------
vultr          not built: URLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)
civo           approved, read ACCEPTE -                               7     0      0    0     0 |    7     0      0    0     0   26.9      4   10
virtua         READY_FOR_REVIEW       stated                          0     0      1    6     0 |    1     0      0    6     0   15.8      4    1
shockbyte      READY_FOR_REVIEW       stated                          0     0      4    3     0 |    4     0      0    3     0   17.9      4    4
wasabi         not built: only 316 characters of text (the page is probably drawn by script)
ably           READY_FOR_REVIEW       stated,value_in_sentence,rep    0     0      5    2     0 |    4     0      1    2     0   51.2      6    4
sinch          READY_FOR_REVIEW       stated                          0     0      3    4     0 |    3     0      0    4     0   28.3      5    3
plivo          FAILED                 -                               0     0      0    7     0 |    0     0      0    7     0    8.7      3    0
gitlab         approved, read ACCEPTE -                               5     0      0    2     0 |    5     0      0    2     0   47.4      5    7
oneuptime      approved, read ACCEPTE -                               7     0      0    0     0 |    7     0      0    0     0   34.2      4   10
supabase       approved, read ACCEPTE -                               4     1      0    2     0 |    4     1      0    2     0   33.2      4    9
neon           approved, read ACCEPTE -                               6     0      0    1     0 |    6     0      0    1     0   37.1      4   10
upstash        approved, read ACCEPTE -                               4     0      1    2     0 |    4     0      1    2     0   22.4      4    7
clickhouse     approved, read ACCEPTE -                               5     0      1    1     0 |    5     0      1    1     0   31.6      4    8
aerospike      READY_FOR_REVIEW       stated,value_in_sentence,rep    0     0      6    1     0 |    4     0      2    1     0   62.5      6    4

returned downstream: 38 correct, 1 wrong, 21 not read, 31 not stated, 0 another service's value
shown to the reviewer: 54 correct, 1 wrong, 5 not read, 31 not stated, 0 another service's value
WRONG (returned) supabase credit_application: key "next_invoice", returned "account_balance"
WRONG (shown) supabase credit_application: key "next_invoice", shown "account_balance"
```

57 Claude calls and 77 Jev calls, 417.2 seconds of builds.

Page by page against the first fresh run (one run each; model output varies between runs, so a difference here is
not shown to come from the prompt change):

| Page | First fresh run | This run |
|:---|:---|:---|
| Civo | Approved, read accepted, 7 correct | Same |
| Virtua, Shockbyte, Sinch | Refused at `stated` | Same |
| Ably | Refused at `stated`, `value_in_sentence`, `reproduce` | Same |
| Plivo | Failed: readers found nothing stated | Same |
| GitLab | Failed: the builder's choice map in the wrong shape | **Changed:** approved, read accepted, 5 correct, 2 not stated |
| OneUptime | Approved, read accepted, 7 correct | Same |
| Supabase | Approved; read refused by Jev's template match (0.66) | **Changed:** read accepted; 4 correct, **1 wrong returned downstream** (below), 2 not stated |
| Neon | Refused: readers split on the claim window | **Changed:** approved, read accepted, 6 correct (claim window 21 days, which the key accepts), 1 not stated |
| Upstash | Approved, read accepted, 4 correct, claim window not read | Same |
| ClickHouse | Refused at `stated`: readers said the commitment is not stated | **Changed:** readers gave 99.9; approved, read accepted, 5 correct, claim window not read |
| Aerospike | Refused at `stated`, `value_in_sentence`, `reproduce` | Same |

Of the three pages whose answer phrase was a prompt example: Upstash kept the same outcome; Ably was refused in both
runs (no percentage tiers); Neon was refused in the first run on its claim window and passed in this one, and its
payment term (the phrase that was an example) was read the same way in both.

**Wrong values in this run.** One, in both views: Supabase, `credit_application`: key `next_invoice`, returned
`account_balance`. The page says Supabase "will issue a credit to Customer's account" and that credits "may only be
applied to future billing charges"; my key took the second, the readers the first. In the first fresh run the same
value was shown to the reviewer but did not go downstream, because that read was refused; this time the read was
accepted, so it is the first wrong value returned downstream in any public-SLA run. It is a reading of an ambiguous
payment term, not a misread number, and the key was not changed.

## What this does not establish

- **One run per table** on **one day's version** of each page; model output varies between runs and no variance was measured.
- **My key.** I wrote it, after seeing the builder's term list; the choices listed above change the counts, and I
  corrected one value after seeing the result.
- **No second contract** was given, so the keyless second-contract check never ran; the one approved template was
  approved by a script, not a person, and read the page it was built from.
- **Thirteen pages, chosen by me**, mostly large cloud and developer vendors whose SLAs are short public web pages.
  Negotiated enterprise SLAs, order-form riders, PDFs and amendments were not tried.
- **"Shown to the reviewer: 0 wrong"** is about the readers' agreed values on 13 pages; it does not mean a reviewer
  would catch a wrong value if one appeared.

## Run it again (first set; add `--set fresh` for the second)

```
uv run --locked python scripts/evaluate_public_slas.py --fetch      # uses the cache; fetches only pages not cached
uv run --locked python scripts/evaluate_public_slas.py --build      # 13 builds, about 60 Claude calls
uv run --locked python scripts/evaluate_public_slas.py --score fixtures/template_builder_public/results/<stamp>.json
```

The pages' text is never committed: results replace every quoted sentence, rule pattern, map phrase, reader reason and
interpreter message with its SHA-256 (and character offsets in the normalized text where found). This page quotes a
few words of the vendors' terms only where a refusal cannot be explained otherwise.
