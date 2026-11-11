"""Real public service-level agreements through the template builder (docs/demo/TEMPLATE-BUILDER-PUBLIC-SLAS.md).

    uv run --locked python scripts/evaluate_public_slas.py --fetch     # fetch (once) and convert; no model call
    uv run --locked python scripts/evaluate_public_slas.py --build     # one build per page, one at a time
    uv run --locked python scripts/evaluate_public_slas.py --score RESULTS.json   # score an existing results file

1. Fetch. Each page in SOURCES is fetched with one plain HTTPS GET (urllib, standard library) the first time only;
   the response bytes and the converted text are cached under ~/uptime-demo/public-slas/ (OUTSIDE the repository,
   because the pages are the vendors' copyrighted terms). Later runs use the cache. The HTML becomes text
   deterministically with html.parser (standard library): script, style and similar elements are dropped, block
   elements end a line, a table row is one line with its cells joined by " | ", and blank lines are removed.
2. The 60,000-character limit. A text over the builder's limit is cut by the source's stated `section` rule: from the
   first line matching `start` to the line before the first later line matching `end` (end of text if none). If the
   cut is still over the limit, or the source states no rule, the page is recorded as too long and not built.
3. Build. Each text is one pasted contract with no second contract, through the Python API (TemplateBuilds.start,
   real Claude Code CLI, real Jev through uptime.jev.JevClient, which reads its own key file; this script never reads
   it). Builds run one at a time. If every blocking check passes, the script approves the template as
   "evaluation-script" (a script, not a person), acknowledging exactly the flagged terms, and reads the same text with
   the approved template through the guarded read; those values are what Uptime would hand downstream. The script stops
   before a build once it has made MAX_CLAUDE_CALLS Claude calls.
4. Score against fixtures/template_builder_public/key.json, written by hand by the evaluating agent after reading each
   cached page (having seen the builder's term list). Per term: correct, wrong (a value was returned and it is not the
   key's), not_read, or not_stated (the key says the page does not state it and nothing was returned). Two views are
   scored: `returned` (the accepted guarded read; a refused build or read returns nothing) and `shown` (the values
   the build showed the reviewer, whether or not it could be approved).

Results: fixtures/template_builder_public/results/<stamp>.json with every quoted sentence, rule pattern, reader
reason and interpreter message replaced by its SHA-256 (and, for sentences found in the text, character offsets in the
normalized text). sources.json records URL, retrieval time, byte count, text SHA-256 and the cut.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from time import perf_counter
import traceback
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uptime import template_builder as tb  # noqa: E402
from uptime import template_rules as rules  # noqa: E402

CACHE = Path(os.path.expanduser("~/uptime-demo/public-slas"))
OUT = ROOT / "fixtures" / "template_builder_public"
LIMIT = tb.PASTE_LIMIT
MAX_CLAUDE_CALLS = 150
REVIEWER = "evaluation-script"
USER_AGENT = "Mozilla/5.0 (compatible; contract-reader-evaluation/1.0)"
MIN_TEXT = 1500  # characters; less than this is recorded as a page with no readable terms (for example script-rendered)

# Real public SLA pages, the vendor's own legal page where one exists. Chosen from memory of where vendors publish
# their SLAs; a URL that answered 404 on the first fetch was replaced once by the vendor's other likely address (the
# 404s stay recorded in the cache's fetch log; DigitalOcean's and MongoDB's second addresses came from a web search). Twilio's index page lists its SLAs; its APIs SLA is used. `section`: the stated cut rule for a page
# whose text is over the limit (regular expressions on whole lines, case-insensitive).
SOURCES = [
    {"id": "aws-ec2", "vendor": "Amazon Web Services", "service": "Amazon Compute (EC2) SLA", "category": "cloud compute",
     "url": "https://aws.amazon.com/compute/sla/"},
    {"id": "aws-s3", "vendor": "Amazon Web Services", "service": "Amazon S3 SLA", "category": "cloud storage",
     "url": "https://aws.amazon.com/s3/sla/"},
    {"id": "gcp-compute", "vendor": "Google Cloud", "service": "Compute Engine SLA", "category": "cloud compute",
     "url": "https://cloud.google.com/compute/sla"},
    {"id": "gcp-storage", "vendor": "Google Cloud", "service": "Cloud Storage SLA", "category": "cloud storage",
     "url": "https://cloud.google.com/storage/sla"},
    {"id": "digitalocean", "vendor": "DigitalOcean", "service": "Droplet Service Level Agreement", "category": "cloud compute",
     "url": "https://docs.digitalocean.com/products/droplets/details/sla/"},
    {"id": "linode", "vendor": "Akamai (Linode)", "service": "Service Level Agreement", "category": "cloud compute",
     "url": "https://www.linode.com/legal-sla/"},
    {"id": "backblaze", "vendor": "Backblaze", "service": "B2 Cloud Storage SLA", "category": "cloud storage",
     "url": "https://www.backblaze.com/company/policy/sla"},
    {"id": "mongodb-atlas", "vendor": "MongoDB", "service": "Atlas SLA", "category": "database",
     "url": "https://www.mongodb.com/cloud/atlas/sla"},
    {"id": "twilio", "vendor": "Twilio", "service": "Twilio APIs Service Level Agreement", "category": "communications API",
     "url": "https://www.twilio.com/en-us/legal/service-level-agreement/twilio-apis"},
    {"id": "mailgun", "vendor": "Mailgun", "service": "Service Level Agreement", "category": "communications API",
     "url": "https://www.mailgun.com/legal/sla/"},
    {"id": "github", "vendor": "GitHub", "service": "Online Services SLA", "category": "developer tools",
     "url": "https://github.com/customer-terms/github-online-services-sla"},
    {"id": "vercel", "vendor": "Vercel", "service": "Service Level Agreement", "category": "developer tools",
     "url": "https://vercel.com/legal/sla"},
    {"id": "atlassian", "vendor": "Atlassian", "service": "Cloud SLA", "category": "SaaS collaboration",
     "url": "https://www.atlassian.com/legal/sla"},
    {"id": "slack", "vendor": "Slack", "service": "Service Level Agreement", "category": "SaaS collaboration",
     "url": "https://slack.com/terms/service-level-agreement"},
    {"id": "zendesk", "vendor": "Zendesk", "service": "Service Level Agreement", "category": "SaaS support",
     "url": "https://www.zendesk.com/company/agreements-and-terms/service-level-agreement/"},
    {"id": "cloudflare", "vendor": "Cloudflare", "service": "Business SLA", "category": "network / CDN",
     "url": "https://www.cloudflare.com/business-sla/"},
]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


# --- HTML to text (standard library, deterministic) ------------------------------------------

DROP = {"script", "style", "noscript", "template", "svg", "head", "iframe", "button", "form", "select", "nav", "footer"}
BLOCK = {"p", "div", "section", "article", "main", "header", "aside", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul",
         "ol", "dl", "dt", "dd", "blockquote", "pre", "table", "thead", "tbody", "tfoot", "caption", "figure",
         "figcaption", "hr", "address", "details", "summary"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.line, self.drop, self.row = [], [], 0, None

    def _end_line(self):
        text = " ".join("".join(self.line).split())
        if text:
            self.lines.append(text)
        self.line = []

    def handle_starttag(self, tag, attrs):
        if tag in DROP:
            self.drop += 1
            return
        if self.drop:
            return
        if tag == "tr":
            self._end_line()
            self.row = []
        elif tag in ("td", "th"):
            if self.row is not None:
                self.line = []
            else:
                self.line.append(" ")
        elif tag == "br":
            if self.row is None:
                self._end_line()
            else:
                self.line.append(" ")
        elif tag in BLOCK and self.row is None:
            self._end_line()

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.drop:
            if self.row is None:
                self._end_line()
            else:
                self.line.append(" ")

    def handle_endtag(self, tag):
        if tag in DROP:
            self.drop = max(0, self.drop - 1)
            return
        if self.drop:
            return
        if tag in ("td", "th") and self.row is not None:
            cell = " ".join("".join(self.line).split())
            self.row.append(cell)
            self.line = []
        elif tag == "tr" and self.row is not None:
            cells = [c for c in self.row if c]
            if cells:
                self.lines.append(" | ".join(cells))
            self.row = None
            self.line = []
        elif tag in BLOCK and self.row is None:
            self._end_line()

    def handle_data(self, data):
        if not self.drop:
            self.line.append(data)

    def text(self):
        self._end_line()
        return "\n".join(self.lines) + "\n"


def html_to_text(html):
    parser = _Text()
    parser.feed(html)
    parser.close()
    return parser.text()


def cut(text, rule):
    """(text, note): the stated section rule applied to text over the limit."""
    if len(text) <= LIMIT:
        return text, None
    if not rule:
        return None, "longer than %s characters (%s) and no section rule is stated; not built" % (format(LIMIT, ","), format(len(text), ","))
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if re.search(rule["start"], line, re.I)), None)
    if start is None:
        return None, "longer than the limit and the section's start line was not found; not built"
    end = next((i for i in range(start + 1, len(lines)) if rule.get("end") and re.search(rule["end"], lines[i], re.I)), len(lines))
    section = "\n".join(lines[start:end]) + "\n"
    note = "cut to lines %d-%d by the stated rule (start %r, end %r): %s of %s characters" % (
        start + 1, end, rule["start"], rule.get("end"), format(len(section), ","), format(len(text), ","))
    if len(section) > LIMIT:
        return None, note + "; still longer than the limit; not built"
    return section, note


def fetch(source):
    """The cached page, fetched once with a plain HTTPS GET if it is not cached yet. -> record dict."""
    CACHE.mkdir(parents=True, exist_ok=True)
    os.chmod(CACHE, 0o700)
    raw_path, meta_path = CACHE / (source["id"] + ".html"), CACHE / (source["id"] + ".json")
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get("url") == source["url"]:
            return meta
    meta = {"id": source["id"], "url": source["url"], "retrieved_at": now(), "status": None, "bytes": None,
            "final_url": None, "error": None}
    try:
        request = urllib.request.Request(source["url"], headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            meta.update(status=response.status, bytes=len(body), final_url=response.geturl(),
                        content_type=response.headers.get("Content-Type"))
        raw_path.write_bytes(body)
    except urllib.error.HTTPError as error:
        meta.update(status=error.code, error="HTTP %d" % error.code)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        meta.update(error=type(error).__name__ + ": " + str(getattr(error, "reason", error))[:200])
    meta_path.write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def prepare(source):
    """Fetch (or use the cache), convert and cut. -> sources.json row, text or None."""
    meta = fetch(source)
    row = {k: source[k] for k in ("id", "vendor", "service", "category", "url")}
    row.update({k: meta.get(k) for k in ("retrieved_at", "status", "bytes", "final_url", "error")})
    raw_path = CACHE / (source["id"] + ".html")
    if meta.get("error") or not raw_path.exists():
        row.update(text_chars=None, text_sha256=None, cut=None, used=False, why_not_used=meta.get("error") or "not fetched")
        return row, None
    body = raw_path.read_bytes()
    row["bytes_sha256"] = hashlib.sha256(body).hexdigest()
    full = html_to_text(body.decode("utf-8", errors="replace"))
    (CACHE / (source["id"] + ".txt")).write_text(full)
    row.update(text_chars=len(full), text_sha256=digest(full))
    text, note = cut(full, source.get("section"))
    row["cut"] = note
    if text is None:
        row.update(used=False, why_not_used=note)
        return row, None
    if len(text) < MIN_TEXT:
        row.update(used=False, why_not_used="only %d characters of text (the page is probably drawn by script)" % len(text))
        return row, None
    (CACHE / (source["id"] + ".used.txt")).write_text(text)
    row.update(used=True, used_chars=len(text), used_sha256=digest(text), why_not_used=None)
    return row, text


# --- Quotes out of the record ----------------------------------------------------------------

QUOTE_KEYS = {"quote", "rule_quote", "conflict", "reason", "sentence", "pattern", "error", "rule_error", "detail",
              "reasons", "summary", "repair_note", "basis"}
OUR_SUMMARIES = re.compile(r"^(\d+ terms, \d+ quotes found|\d+ extraction rules written|\d+ of \d+ checks passed|"
                           r"No approved template|Waiting for|Approved by|Read by the approved|Approval is blocked|"
                           r"\d+ of \d+$|Only \d+ of 3 Claude readers|Not started)")


def hashed(value, normalized):
    """A string as {"sha256", "chars"} plus its offsets when it is in the normalized text."""
    out = {"sha256": digest(value), "chars": len(value)}
    found = normalized.find(rules.normalize(value)) if value.strip() else -1
    if found >= 0:
        out.update(start=found, end=found + len(rules.normalize(value)))
    return out


def scrub(value, normalized, key=None):
    """Replace every quoted string (and anything that could carry the vendor's words) by its hash."""
    if isinstance(value, dict) and key == "map":  # a choice rule's phrases are the contract's words
        return [{"phrase": hashed(k, normalized), "option": v} for k, v in value.items()]
    if isinstance(value, dict):
        return {k: scrub(v, normalized, k) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, normalized, key) for v in value]
    if isinstance(value, str) and key in QUOTE_KEYS:
        if key in ("summary", "detail") and (OUR_SUMMARIES.match(value) or re.fullmatch(r"[\d.]+", value)):
            return value
        return hashed(value, normalized)
    return value


# --- Build -----------------------------------------------------------------------------------

class Counter_:
    """Counts every Claude CLI call the engine makes (as the held-out script does) and every Jev call."""

    def __init__(self):
        self.calls, self.original = [], tb.ClaudeCLI.__call__
        counter = self

        def counted(cli, system, prompt, *args, **kwargs):
            model = kwargs.get("model") or (args[0] if args else None) or cli.model
            started = perf_counter()
            try:
                answer = counter.original(cli, system, prompt, *args, **kwargs)
            except Exception as exc:
                counter.calls.append({"model": model, "seconds": round(perf_counter() - started, 1), "ok": False,
                                      "error": type(exc).__name__})
                raise
            counter.calls.append({"model": model, "seconds": round(perf_counter() - started, 1), "ok": True})
            return answer
        tb.ClaudeCLI.__call__ = counted

    def restore(self):
        tb.ClaudeCLI.__call__ = self.original


class CountingJev:
    def __init__(self, inner):
        self.inner, self.calls = inner, []

    def _wrap(self, name, *args):
        started = perf_counter()
        try:
            answer = getattr(self.inner, name)(*args)
        except Exception as exc:
            self.calls.append({"method": name, "seconds": round(perf_counter() - started, 2), "ok": False,
                               "error": type(exc).__name__})
            raise
        self.calls.append({"method": name, "seconds": round(perf_counter() - started, 2), "ok": True})
        return answer

    def choice(self, question, options, context):
        return self._wrap("choice", question, options, context)

    def yes_no(self, question, context):
        return self._wrap("yes_no", question, context)


def build_one(source, text, executable, jev_client, folder, counter):
    record = {"id": source["id"], "error": None}
    jev = CountingJev(jev_client)
    service = tb.TemplateBuilds(folder / source["id"], tb.ClaudeCLI(executable), jev, background=False)
    first_call = len(counter.calls)
    started = perf_counter()
    try:
        build = service.start(contract={"title": source["service"], "vendor": source["vendor"], "text": text}, consent=True)
        record["build_seconds"] = round(perf_counter() - started, 1)
        record["state"] = build["state"]
        blocking = [c for c in build.get("checks") or [] if c.get("blocking")]
        record["blocking_failed"] = [c["id"] for c in blocking if not c["ok"]]
        record["checks"] = [{k: c.get(k) for k in ("id", "passed", "total", "ok", "blocking", "ran", "not_stated")}
                            for c in build.get("checks") or []]
        record["terms"] = [{k: t.get(k) for k in ("field", "stated", "status", "value", "display", "agreement",
                                                  "value_in_sentence", "rule_value", "needs_acknowledgement", "quote",
                                                  "reason", "conflict", "rule", "rule_error", "readers", "jev")}
                           for t in build.get("terms") or []]
        record["steps"] = [{k: s.get(k) for k in ("id", "state", "seconds", "model", "summary")} for s in build["steps"]]
        record["build_error"] = build.get("error")
        record["template"] = build.get("template")
        record["approved"] = False
        ready = build["state"] == "READY_FOR_REVIEW" and build.get("template") and blocking and not record["blocking_failed"]
        if ready:
            ack = [t["field"] for t in build["terms"] if t.get("needs_acknowledgement")]
            approved = service.approve(build["id"], build["template"]["sha256"], REVIEWER, ack)
            record.update(approved=approved["state"] == "APPROVED", acknowledged=ack)
            reading = service.read(build["id"], document={"title": source["service"], "vendor": source["vendor"], "text": text})
            record["reading"] = {k: reading.get(k) for k in ("status", "found", "total", "not_stated", "reasons", "guards",
                                                             "jev_template", "milliseconds", "model_calls")}
            record["reading"]["terms"] = [{k: t.get(k) for k in ("field", "value", "display", "quote", "stated", "error",
                                                                 "failed_guards")} for t in reading["terms"]]
    except Exception as exc:  # recorded; the next page still runs
        record["error"] = {"type": type(exc).__name__, "sentence": str(exc)[:300], "traceback": traceback.format_exc()[-1500:]}
    record["seconds"] = round(perf_counter() - started, 1)
    record["claude_calls"] = counter.calls[first_call:]
    record["jev_calls"] = jev.calls
    return record


# --- Score -----------------------------------------------------------------------------------

FIELDS = [t["field"] for t in rules.TERMS]
KINDS = ("correct", "wrong", "not_read", "not_stated", "other_service")


def outcome(value, want, other=(), also=()):
    """correct, wrong, not_read, not_stated, or other_service (the value the page states for another service)."""
    if want == "not_stated":
        return "not_stated" if value is None else "wrong"
    if value is None:
        return "not_read"
    if rules.same(value, want) or any(rules.same(value, a) for a in also):
        return "correct"
    if any(rules.same(value, o) for o in other):
        return "other_service"
    return "wrong"


def score(record, key):
    """Per term, two views: what was returned downstream (an accepted read) and what the reviewer was shown."""
    want = key["terms"]
    accepted = (record.get("reading") or {}).get("status") == "ACCEPTED"
    returned = {t["field"]: t["value"] for t in (record.get("reading") or {}).get("terms") or []} if accepted else {}
    shown = {t["field"]: t["value"] for t in record.get("terms") or []}
    other, also = key.get("other_service") or {}, key.get("also_correct") or {}
    rows = []
    for f in FIELDS:
        rows.append({"field": f, "key": want[f], "returned": returned.get(f), "shown": shown.get(f),
                     "returned_outcome": outcome(returned.get(f), want[f], other.get(f, ()), also.get(f, ())),
                     "shown_outcome": outcome(shown.get(f), want[f], other.get(f, ()), also.get(f, ()))})
    counts = {view: {k: sum(1 for r in rows if r[view + "_outcome"] == k) for k in KINDS}
              for view in ("returned", "shown")}
    return {"terms": rows, "counts": counts}


def summarize(run, key):
    lines = []
    head = "%-14s %-22s %-28s %4s %5s %6s %4s %5s | %4s %5s %6s %4s %5s %6s %6s %4s" % (
        "page", "build", "refused at", "ok", "wrong", "unread", "n/s", "other", "ok", "wrong", "unread", "n/s", "other",
        "secs", "claude", "jev")
    lines.append("%-66s %s | %s" % ("", "returned downstream (accepted read)", "shown to the reviewer"))
    lines.append(head)
    lines.append("-" * len(head))
    wrong = []
    totals = {v: {k: 0 for k in KINDS} for v in ("returned", "shown")}
    for r in run["pages"]:
        if not r.get("built"):
            lines.append("%-14s %s" % (r["id"], "not built: " + (r.get("why_not_used") or "")))
            continue
        s = r["score"]
        for v in totals:
            for k in totals[v]:
                totals[v][k] += s["counts"][v][k]
        state = r.get("state") or "ERROR"
        if r.get("reading"):
            state = "approved, read " + r["reading"]["status"]
        where = ",".join(r.get("blocking_failed") or []) or ("-" if not (r.get("reading") or {}).get("status") == "REFUSED"
                                                              else "read guards: " + ",".join(
                                                                  g["id"] for g in r["reading"]["guards"] if not g["ok"] and not g.get("advisory")))
        cr, cs = s["counts"]["returned"], s["counts"]["shown"]
        lines.append("%-14s %-22s %-28s %4d %5d %6d %4d %5d | %4d %5d %6d %4d %5d %6.1f %6d %4d" % (
            r["id"], state[:22], where[:28], cr["correct"], cr["wrong"], cr["not_read"], cr["not_stated"], cr["other_service"],
            cs["correct"], cs["wrong"], cs["not_read"], cs["not_stated"], cs["other_service"], r["seconds"],
            len(r["claude_calls"]), len(r["jev_calls"])))
        for t in s["terms"]:
            for view in ("returned", "shown"):
                if t[view + "_outcome"] in ("wrong", "other_service"):
                    wrong.append((view, r["id"], t["field"], t["key"], t[view], t[view + "_outcome"]))
    lines.append("")
    for v in ("returned", "shown"):
        lines.append("%s: %d correct, %d wrong, %d not read, %d not stated, %d another service's value" % (
            "returned downstream" if v == "returned" else "shown to the reviewer", totals[v]["correct"], totals[v]["wrong"],
            totals[v]["not_read"], totals[v]["not_stated"], totals[v]["other_service"]))
    for view, page, field, want, got, kind in wrong:
        lines.append("%s (%s) %s %s: key %s, %s %s" % ("WRONG" if kind == "wrong" else "OTHER SERVICE", view, page, field,
                                                       json.dumps(want), "returned" if view == "returned" else "shown", json.dumps(got)))
    return "\n".join(lines), totals, wrong


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--score", default=None)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.score:
        run = json.loads(Path(args.score).read_text())
        key = {k: v for k, v in json.loads((OUT / "key.json").read_text()).items() if not k.startswith("_")}
        for r in run["pages"]:
            if r.get("built"):
                r["score"] = score(r, key[r["id"]])
        text, totals, wrong = summarize(run, key)
        run["summary"] = {"totals": totals, "wrong": [dict(zip(("view", "page", "field", "key", "value", "outcome"), w)) for w in wrong],
                          "table": text}
        Path(args.score).write_text(json.dumps(run, indent=1) + "\n")
        print(text)
        return
    rows, texts = [], {}
    for source in SOURCES:
        row, text = prepare(source)
        rows.append(row)
        if text is not None:
            texts[source["id"]] = text
        print("%-14s %-6s %8s bytes %8s chars %s" % (source["id"], row.get("status"), row.get("bytes"), row.get("text_chars"),
                                                     "used" if row["used"] else "NOT USED: " + str(row["why_not_used"])))
    (OUT / "sources.json").write_text(json.dumps({"fetched_with": "urllib.request GET, User-Agent %r" % USER_AGENT,
                                                  "cache": "~/uptime-demo/public-slas (outside the repository)",
                                                  "limit_chars": LIMIT, "sources": rows}, indent=1) + "\n")
    if not args.build:
        return
    executable = shutil.which("claude")
    if not executable:
        sys.exit("No Claude Code CLI found on PATH.")
    from uptime.jev import JevClient
    key_path = OUT / "key.json"
    key = {k: v for k, v in json.loads(key_path.read_text()).items() if not k.startswith("_")} if key_path.exists() else {}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (OUT / "results").mkdir(exist_ok=True)
    out = OUT / "results" / (stamp + ".json")
    commit = None
    try:
        import subprocess
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        pass
    run = {"started_at": now(), "engine_commit": commit, "reviewer": REVIEWER,
           "reviewer_note": "Approvals were made by a script named evaluation-script, not by a person.",
           "quotes_note": "Every quoted sentence, rule pattern, reader reason and interpreter message is replaced by its "
                          "SHA-256 (with character offsets in the normalized text where it is found there).",
           "pages": []}
    counter = Counter_()
    jev_client = JevClient()
    work = CACHE / "runs" / stamp
    work.mkdir(parents=True, exist_ok=True)
    try:
        for row in rows:
            page = {"id": row["id"], "built": False, "why_not_used": row.get("why_not_used")}
            if row["id"] not in texts:
                run["pages"].append(page)
                continue
            if len(counter.calls) >= MAX_CLAUDE_CALLS:
                page["why_not_used"] = "stopped: %d Claude calls made" % len(counter.calls)
                run["pages"].append(page)
                continue
            print("%s: building ..." % row["id"], flush=True)
            text = texts[row["id"]]
            record = build_one(next(s for s in SOURCES if s["id"] == row["id"]), text, executable, jev_client, work, counter)
            normalized = rules.normalize(text)
            page.update(scrub(record, normalized), built=True)
            if row["id"] in key:
                page["score"] = score(page, key[row["id"]])
            run["pages"].append(page)
            out.write_text(json.dumps(run, indent=1) + "\n")
            print("  %s in %.1f s, %d Claude calls, %d Jev calls%s" % (
                record.get("state"), record["seconds"], len(record["claude_calls"]), len(record["jev_calls"]),
                ("; error: " + record["error"]["sentence"]) if record["error"] else ""), flush=True)
    finally:
        counter.restore()
    run["finished_at"] = now()
    run["claude_calls"] = len(counter.calls)
    run["jev_calls"] = sum(len(p.get("jev_calls") or []) for p in run["pages"])
    if key:
        text, totals, wrong = summarize(run, key)
        run["summary"] = {"totals": totals, "wrong": [dict(zip(("view", "page", "field", "key", "value", "outcome"), w)) for w in wrong],
                          "table": text}
        print(text)
    out.write_text(json.dumps(run, indent=1) + "\n")
    print("calls: %d Claude, %d Jev" % (run["claude_calls"], run["jev_calls"]))
    print("results:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
