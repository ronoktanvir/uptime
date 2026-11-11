# Template builder: real public service-level agreements

A judge wrote that the template builder "has not read a contract it wasn't written for". The held-out evaluation
(`TEMPLATE-BUILDER-HELDOUT.md`) used contracts written by other Claude calls. This page is the first time real vendor
SLAs went through it: 13 public SLA pages from 11 vendors, one build each, on November 11, 2026 (UTC), with the
version 3 engine (commit `1fa66d2`: a credit schedule of one to six tiers, durations in the contract's own unit).
Nothing in the engine, its prompts or its thresholds was changed after seeing these pages. The result is published as
it came out.

**Headline.** One of 13 pages (MongoDB Atlas) produced a template that passed every blocking check; the script
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

## What the builder cannot express at all

- **Credits that are not percentage tiers**: a rate per unit of downtime (Mailgun: a percentage per 30 minutes), a
  formula (Cloudflare: outage minutes times the share of affected visitors), or credits in days of service. The
  schedule is "below X% earns Y%"; these are recorded as not stated, and `stated` then refuses the template.
- **Several commitments in one document**: per region or instance (AWS EC2), storage class (AWS S3, Google Cloud
  Storage), network tier or machine family (Google Compute), plan (Atlassian, Twilio). A template has one commitment
  and one schedule. Every build took the first one listed; the others are lost, never mixed (no "other service" value
  appeared).
- **A commitment stated only through the credit table** (AWS S3; MongoDB's readers did give the table's top
  threshold). Readers say it is not stated, which blocks the template.
- **Deadlines that are calendar points**, not a number and a unit: "by the end of the month following", "by the end
  of the second billing cycle". Readers said not stated (MongoDB, AWS, Cloudflare) or 2 months (DigitalOcean's "within
  two billing cycles" was not read either). The money link also refuses any claim window not in calendar days.
- **Caps in other units**: 90 days of service per quarter (GitHub), one month of fees per twelve months (Cloudflare).
- **A payment term with two outcomes** (GitHub: refund or account credit). A choice term has one option.
- **Tier tables whose cells are not rows of one line** (Vercel's ranges and credits on separate lines), and **tiers
  stated through defined terms** (held-out forms 4 and 6): a tier must have its credit, and its threshold or the
  commitment, in one sentence or line.
- **Ranges with inclusive upper ends and gaps** (Vercel "99.1% to 99.98%", "95% to 99%"): "below X" tiers are an
  approximation.
- **Pages drawn by script** (Slack), PDFs and scans: the fetcher reads HTML text only.

## What this does not establish

- **One run** on **one day's version** of each page; model output varies between runs and no variance was measured.
- **My key.** I wrote it, after seeing the builder's term list; the choices listed above change the counts, and I
  corrected one value after seeing the result.
- **No second contract** was given, so the keyless second-contract check never ran; the one approved template was
  approved by a script, not a person, and read the page it was built from.
- **Thirteen pages, chosen by me**, mostly large cloud and developer vendors whose SLAs are short public web pages.
  Negotiated enterprise SLAs, order-form riders, PDFs and amendments were not tried.
- **"Shown to the reviewer: 0 wrong"** is about the readers' agreed values on 13 pages; it does not mean a reviewer
  would catch a wrong value if one appeared.

## Run it again

```
uv run --locked python scripts/evaluate_public_slas.py --fetch      # uses the cache; fetches only pages not cached
uv run --locked python scripts/evaluate_public_slas.py --build      # 13 builds, about 60 Claude calls
uv run --locked python scripts/evaluate_public_slas.py --score fixtures/template_builder_public/results/<stamp>.json
```

The pages' text is never committed: results replace every quoted sentence, rule pattern, map phrase, reader reason and
interpreter message with its SHA-256 (and character offsets in the normalized text where found). This page quotes a
few words of the vendors' terms only where a refusal cannot be explained otherwise.
