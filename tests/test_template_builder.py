"""Demo line: the template builder (docs/demo/TEMPLATE-BUILDER.md, including "Version 2") with a fake Claude and a
fake Jev.

No network, no Claude Code CLI: `claude(system, prompt, model=...)` and Jev are stand-ins defined here. The
interpreter, the routing, the checks, approval by SHA-256 with acknowledgement and the guarded reads are the real code.
The authored answer key (expected.json) is used here only, to make the fake readers answer and to check results.
"""
from decimal import Decimal
import json
import os
import re

from fastapi.testclient import TestClient
import pytest

from scripts import setup_northwind as setup
from uptime import template_builder as tb
from uptime import template_rules as rules
from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient
from uptime.template_builder import FIXTURES, TemplateBuilds, TemplateRefused

EXPECTED = json.loads((FIXTURES / "expected.json").read_text())
SAMPLE = "halcyon-availability-addendum"
RAW = {d: (FIXTURES / ("halcyon-%s.txt" % d)).read_text() for d in "abc"}
TEXT_A = rules.normalize(RAW["a"])
ROLES = {"clause_by_clause": 1, "numbers_first": 2, "sceptic": 3}

GOOD_RULES = {
    "availability_target_percent": {"pattern": r"Platform Availability of at least (\d+(?:\.\d+)?)%"},
    "measurement_period": {"pattern": r'"Measurement Period" means each (calendar \w+)',
                           "map": {"calendar month": "calendar_month"}},
    "credit_schedule": {"rows": [{"pattern": r"where Platform Availability is less than (?P<below>\d+(?:\.\d+)?)%[^,;]*, "
                                             r"a Service Credit of (?P<credit>\d+(?:\.\d+)?)%"}]},
    "credit_cap_percent": {"pattern": r"will not exceed [a-z-]+ percent \((\d+(?:\.\d+)?)%\)"},
    "claim_window": {"pattern": r"submit a written claim to \S+ within [a-z-]+ \((?P<value>\d+)\) (?P<unit>days|business days)"},
    "maintenance_notice": {"pattern": r"scheduled maintenance on the Covered Services, provided that it gives "
                                      r"Customer at least [a-z-]+ \((?P<value>\d+)\) (?P<unit>hours|days|business days)"},
    "credit_application": {"pattern": r"Service Credits will be applied as a credit (against the next invoice)",
                           "map": {"against the next invoice": "next_invoice"}},
}


def quote_for(field, text=TEXT_A):
    """The sentence of a document that a careful reader would quote, found with the good rule."""
    found = rules.run_rule({"field": field, **GOOD_RULES[field]}, rules.normalize(text))
    assert found["value"] is not None, field
    return found["quote"]


def reader_item(field, value, quote, phrase=None):
    """One term as a reader answers it (version 3 shapes): a schedule's tiers carry their own sentences, a duration
    its unit."""
    kind = rules.TERM[field]["type"]
    if kind == "schedule":
        return {"value": [{"below": r["below_percent"], "credit": r["credit_percent"], "quote": q} for r, q in zip(value, quote)],
                "quote": None}
    if kind == "duration":
        return {"value": value["value"], "unit": value["unit"], "quote": quote}
    if kind == "choice":
        return {"value": value, "phrase": phrase, "quote": quote}
    return {"value": value, "quote": quote}


def reader_terms(doc):
    return {f: reader_item(f, v, quote_for(f, RAW[doc]), phrase_for(f, RAW[doc])) for f, v in EXPECTED["halcyon-" + doc]["terms"].items()}


def phrase_for(field, text=TEXT_A):
    """For a choice term, the contract's own words the good rule captures ("calendar month", "against the next invoice")."""
    if rules.TERM[field]["type"] != "choice":
        return None
    return rules.run_rule({"field": field, **GOOD_RULES[field]}, rules.normalize(text))["raw"]


def which(prompt):
    """Which shipped document a prompt carries ('a', 'b' or 'c'), by its customer."""
    contract = prompt.split("CONTRACT\n<<<\n", 1)[1]
    for d, name in (("a", "Save Time Inc"), ("b", "Larkspur Analytics"), ("c", "Brightwater Freight")):
        if name in contract.split(">>>")[0]:
            return d
    return None


class FakeClaude:
    """Answers reader, builder and repair prompts as the real ones are shaped; records every call.

    `reader_override` = {field: {reader index: {value, quote}}} on the first contract; `second_override` the same on
    the second contract; `fail_reader` = reader indices that answer badly on the first contract."""

    def __init__(self, reader_override=None, builder_rules=None, repair_rules=None, fail_reader=(), second_override=None):
        self.calls, self.prompts = [], []
        self.reader_override = reader_override or {}
        self.second_override = second_override or {}
        self.builder_rules = builder_rules or GOOD_RULES
        self.repair_rules = repair_rules or GOOD_RULES
        self.fail_reader = set(fail_reader)

    def __call__(self, system, prompt, model=None):
        self.prompts.append(prompt)
        if prompt.startswith("Read the contract below"):
            role = re.search(r"Your role: (\w+)\.", prompt).group(1)
            index, doc = ROLES[role], which(prompt)
            self.calls.append(("reader", role, doc, model))
            if doc == "a" and index in self.fail_reader:
                return "Sorry, I cannot help with that."
            terms = reader_terms(doc)
            override = self.reader_override if doc == "a" else self.second_override
            for field, by_reader in override.items():
                if index in by_reader:
                    terms[field] = dict(by_reader[index])
            if role == "sceptic":
                for item in terms.values():
                    item.setdefault("conflict", None)
            answer = {"terms": terms}
            if role == "numbers_first":
                answer["numbers"] = [{"number": "99.95%", "governs": "the availability commitment"}]
            return "```json\n" + json.dumps(answer) + "\n```"
        fields = re.search(r"with exactly these fields: ([a-z_, 0-9]+)\.", prompt).group(1).split(", ")
        repair = prompt.startswith("Some extraction rules")
        self.calls.append(("repair" if repair else "builder", None, None, model))
        source = self.repair_rules if repair else self.builder_rules
        return json.dumps({"rules": {f: source[f] for f in fields}})

    def readers(self, doc=None):
        return [c for c in self.calls if c[0] == "reader" and (doc is None or c[2] == doc)]


class FakeJev:
    """Jev's two methods. `choose(options, context)` picks an option (default: the first, a template when one is
    approved); `no` / `low` = substrings of a per-term question answered no / at 0.85."""

    def __init__(self, unreachable=False, probability="0.97", choose=None, choice_probability="0.95", no=(), low=()):
        self.unreachable, self.probability, self.calls = unreachable, Decimal(probability), []
        self.choose = choose or (lambda options, context: options[0])
        self.choice_probability = Decimal(choice_probability)
        self.no, self.low = no, low

    def choice(self, question, options, context):
        self.calls.append(("choice", question, list(options), context))
        if self.unreachable:
            raise ConnectionError("no route")
        assert len(question) <= 1000 and all(len(o) <= 200 for o in options) and len(context) <= 6000
        return {"choice": self.choose(options, context), "probability": self.choice_probability,
                "model": "jev-test", "milliseconds": 1}

    def yes_no(self, question, context):
        self.calls.append(("yes_no", question, context))
        if self.unreachable:
            raise ConnectionError("no route")
        if any(s in question for s in self.no):
            return {"yes": False, "probability": Decimal("0.12"), "model": "jev-test", "milliseconds": 1}
        if any(s in question for s in self.low):
            return {"yes": True, "probability": Decimal("0.85"), "model": "jev-test", "milliseconds": 1}
        return {"yes": True, "probability": self.probability, "model": "jev-test", "milliseconds": 1}


def unrecognised(options, context):
    return "unrecognised"


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    base = tmp_path_factory.mktemp("tb")
    app, private, events = setup.prepare(base / "ws", DEFAULT_ORIGIN)
    with TestClient(app, base_url=private["origin"], client=("127.0.0.1", 1234)) as client:
        actor = ReviewerClient(client, private["origin"], SCRIPT, private["rehearsal_secret"])
        yield app, client, actor, base


def run(served, tmp_path, claude, jev):
    app, client, actor, _ = served
    app.state.template_builds = TemplateBuilds(tmp_path / "template-builds", claude, jev, background=False)
    response = actor.post("/api/template-builds", {"sample_id": SAMPLE})
    assert response.status_code == 202, response.text
    return response.json()["build"]


def engine(tmp_path, claude=None, jev=None):
    return TemplateBuilds(tmp_path / "template-builds", claude or FakeClaude(), jev or FakeJev(), background=False)


def approved(tmp_path, claude=None, jev=None):
    """An engine with one approved template built from the sample."""
    builds = engine(tmp_path, claude, jev)
    build = builds.start(SAMPLE)
    assert build["state"] == "READY_FOR_REVIEW", build
    build = builds.approve(build["id"], build["template"]["sha256"], "test-reviewer",
                           [t["field"] for t in build["terms"] if t["needs_acknowledgement"]])
    return builds, build


def check(build, ident):
    return next(c for c in build["checks"] if c["id"] == ident)


def guard(reading, ident):
    return next(g for g in reading["guards"] if g["id"] == ident)


def stat_mode(path):
    return os.stat(path).st_mode & 0o777


def edited(old, new, text=None):
    text = RAW["a"] if text is None else text
    assert old in text
    return text.replace(old, new)


# --- Version 1 behaviour, kept ---------------------------------------------------------------

def test_off_without_the_flag(served):
    app, client, actor, _ = served
    app.state.template_builds = None
    answer = client.get("/api/template-builds", headers=actor.headers).json()
    assert answer["enabled"] is False and answer["reason"]
    assert actor.post("/api/template-builds", {"sample_id": SAMPLE}).status_code == 404


def test_happy_path_approval_and_the_template_reads_document_c(served, tmp_path):
    app, client, actor, _ = served
    claude, jev = FakeClaude(), FakeJev()
    build = run(served, tmp_path, claude, jev)
    assert build["state"] == "READY_FOR_REVIEW"
    assert [s["id"] for s in build["steps"]] == ["classify", "reader-1", "reader-2", "reader-3", "build", "checks", "review"]
    assert [s["state"] for s in build["steps"]] == ["DONE"] * 6 + ["PENDING"]
    assert build["steps"][0]["detail"]["choice"] == "unrecognised"
    assert build["source"] == {"kind": "sample", "title": "Halcyon Grid: Platform Availability Addendum",
                               "vendor": "Halcyon Grid Services", "chars": len(RAW["a"])}
    assert build["second"]["provided"] is True and build["matched_template"] is None and build["readings"] == []
    assert [c["id"] for c in build["checks"]] == ["stated", "quotes", "value_in_sentence", "agreement", "reproduce",
                                                  "second_document", "jev"]
    assert all(c["not_stated"] == 0 for c in build["checks"]) and check(build, "stated")["passed"] == 2
    assert all(t["stated"] for t in build["terms"]) and build["template"]["not_stated"] == []
    assert all(c["ok"] for c in build["checks"]), build["checks"]
    assert check(build, "quotes")["total"] == 24 and check(build, "jev")["ran"] is True  # 6 terms + 2 tiers, 3 readers
    assert {t["field"]: t["value"] for t in build["terms"]} == EXPECTED["halcyon-a"]["terms"]
    assert all(t["status"] == "PASS" and not t["needs_acknowledgement"] and t["value_in_sentence"] for t in build["terms"])
    assert build["terms"][0]["display"] == "99.95%" and build["terms"][0]["jev"]["probability"] == "0.97"
    assert [c[0] for c in claude.calls].count("reader") == 6 and [c[0] for c in claude.calls].count("builder") == 1
    listing = client.get("/api/template-builds", headers=actor.headers).json()
    assert listing["enabled"] and listing["samples"][0]["document"]["text_url"].endswith("halcyon-a.txt")
    assert "_path" not in json.dumps(listing) and "_expected" not in json.dumps(listing) and "_text_path" not in json.dumps(listing)
    text = client.get(listing["samples"][0]["document"]["text_url"], headers=actor.headers)
    assert text.status_code == 200 and "Platform Availability Addendum".upper() in text.text
    sha = build["template"]["sha256"]
    approved_ = actor.post(f"/api/template-builds/{build['id']}/approve", {"template_sha256": sha, "acknowledged": []})
    assert approved_.status_code == 200, approved_.text
    approved_ = approved_.json()["build"]
    assert approved_["state"] == "APPROVED" and approved_["template"]["approved_by"] == SCRIPT
    calls_before = len(claude.calls)
    reading = actor.post(f"/api/template-builds/{build['id']}/read", {"document_id": "halcyon-c"}).json()["reading"]
    assert reading["model_calls"] == 0 and reading["read_by"] == "TEMPLATE" and len(claude.calls) == calls_before
    assert reading["status"] == "ACCEPTED" and all(g["ok"] for g in reading["guards"]), reading["guards"]
    assert reading["jev_template"]["choice"] == build["template"]["id"] and reading["agreement"] is None
    assert {t["field"]: t["value"] for t in reading["terms"]} == EXPECTED["halcyon-c"]["terms"]
    assert reading["found"] == reading["total"] == 7 and reading["template"]["sha256"] == sha
    assert all(q and q in rules.normalize(RAW["c"]) for t in reading["terms"]
               for q in (t["quote"] if isinstance(t["quote"], list) else [t["quote"]]))
    stored = tmp_path / "template-builds" / (build["id"] + ".json")
    assert stat_mode(stored) == 0o600
    assert [r["id"] for r in json.loads(stored.read_text())["readings"]] == [reading["id"]]


def test_only_the_listed_sample_texts_are_served(served):
    client, actor = served[1], served[2]
    assert client.get("/fixtures/template_builder_demo/halcyon-a.txt", headers=actor.headers).status_code == 200
    for name in ("expected.json", "samples.json", "README.md", "halcyon-z.txt"):
        assert client.get("/fixtures/template_builder_demo/" + name, headers=actor.headers).status_code == 404, name


def test_reader_disagreement_marks_the_term_for_review(served, tmp_path):
    override = {"credit_cap_percent": {3: {"value": "25", "quote": quote_for("credit_cap_percent")}}}
    build = run(served, tmp_path, FakeClaude(reader_override=override), FakeJev())
    term = next(t for t in build["terms"] if t["field"] == "credit_cap_percent")
    assert term["value"] == "30" and term["agreement"] == {"agree": 2, "of": 3} and term["status"] == "REVIEW"
    assert check(build, "agreement")["ok"] is False and check(build, "agreement")["blocking"] is False
    assert build["state"] == "READY_FOR_REVIEW"


def test_a_quote_not_in_the_contract_blocks_approval(served, tmp_path):
    invented = {"claim_window": {2: {"value": "30", "unit": "days", "quote": "Claims may be filed within thirty days."}}}
    build = run(served, tmp_path, FakeClaude(reader_override=invented), FakeJev())
    quotes = check(build, "quotes")
    assert quotes["ok"] is False and quotes["passed"] == 23 and quotes["total"] == 24
    response = served[2].post(f"/api/template-builds/{build['id']}/approve",
                              {"template_sha256": build["template"]["sha256"], "acknowledged": []})
    assert response.status_code == 409 and "blocking check" in response.json()["detail"]


def test_a_rule_that_fails_on_the_second_document_is_repaired(served, tmp_path):
    hardwired = dict(GOOD_RULES, claim_window={"pattern": r"within (?P<value>thirty) \(\d+\) (?P<unit>days) after the end"})
    claude = FakeClaude(builder_rules=hardwired)
    build = run(served, tmp_path, claude, FakeJev())
    repair = [p for p in claude.prompts if p.startswith("Some extraction rules")]
    assert len(repair) == 1 and "claim_window" in repair[0] and "SECOND CONTRACT" in repair[0]
    assert '"45"' not in repair[0]  # never shown the second contract's value
    assert build["steps"][4]["detail"]["repair_rounds"] == 1
    assert check(build, "second_document")["ok"] and check(build, "reproduce")["ok"]


def test_wrong_hash_and_read_before_approval_answer_409(served, tmp_path):
    build = run(served, tmp_path, FakeClaude(), FakeJev())
    actor = served[2]
    early = actor.post(f"/api/template-builds/{build['id']}/read", {"document_id": "halcyon-c"})
    assert early.status_code == 409
    wrong = actor.post(f"/api/template-builds/{build['id']}/approve", {"template_sha256": "0" * 64})
    assert wrong.status_code == 409 and "not this build's template" in wrong.json()["detail"]


def test_two_readers_failing_fails_the_build(served, tmp_path):
    build = run(served, tmp_path, FakeClaude(fail_reader={1, 2}), FakeJev())
    assert build["state"] == "FAILED" and "at least 2" in build["error"]["sentence"]


def test_a_build_running_at_shutdown_loads_as_failed(tmp_path):
    folder = tmp_path / "template-builds"
    builds = TemplateBuilds(folder, FakeClaude(), FakeJev(), background=False)
    build = builds.start(SAMPLE)
    stored = json.loads((folder / (build["id"] + ".json")).read_text())
    stored["state"] = "READING"
    (folder / (build["id"] + ".json")).write_text(json.dumps(stored))
    again = TemplateBuilds(folder, FakeClaude(), FakeJev(), background=False).get(build["id"])
    assert again["state"] == "FAILED" and "server stopped" in again["error"]["sentence"]


def test_interpreter_guards():
    timed = rules.run_rule({"field": "credit_cap_percent", "pattern": r"(a+)+b"}, "a" * 40)
    assert timed["value"] is None and "longer than" in timed["error"]
    hard = rules.run_rule({"field": "claim_window", "pattern": r"within thirty \((?P<value>30)\) (?P<unit>days)"}, TEXT_A)
    assert hard["value"] is None and "spells out" in hard["error"]
    assert "compile" in rules.run_rule({"field": "credit_cap_percent", "pattern": "(unclosed"}, TEXT_A)["error"]
    assert "exactly one" in rules.run_rule({"field": "credit_cap_percent", "pattern": "within"}, TEXT_A)["error"]
    assert "named groups" in rules.run_rule({"field": "claim_window", "pattern": r"within [a-z]+ \((\d+)\)"}, TEXT_A)["error"]
    assert rules.canonical("percent", "99.50%") == "99.5" and rules.canonical("percent", "abc") is None


# --- Version 2: the interpreter refuses ambiguity; value and plausibility checks ------------------

def test_a_rule_matching_two_places_with_different_values_reads_nothing():
    loose = rules.run_rule({"field": "availability_target_percent", "pattern": r"less than (\d+(?:\.\d+)?)%"}, TEXT_A)
    assert loose["value"] is None and loose["ambiguous"] is True and loose["places"] == 2
    assert "matched in 2 places with 2 different values" in loose["error"]
    days = rules.run_rule({"field": "claim_window", "pattern": r"within [a-z-]+ \((?P<value>\d+)\) (?P<unit>days)"}, TEXT_A)
    assert days["value"] is None and days["ambiguous"] and days["places"] == 3  # claim 30, payment 45, termination notice 30


def test_identical_values_in_several_places_are_accepted():
    twice = TEXT_A + " " + quote_for("credit_cap_percent")
    found = rules.run_rule({"field": "credit_cap_percent", **GOOD_RULES["credit_cap_percent"]}, rules.normalize(twice))
    assert found["value"] == "30" and found["places"] == 2 and found["ambiguous"] is False and found["error"] is None


def test_value_in_sentence_digits_words_and_choices():
    days = lambda n, unit="days": {"value": n, "unit": unit}
    assert rules.value_in_sentence("claim_window", days("60"), "within sixty (60) days after the end")
    assert rules.value_in_sentence("maintenance_notice", days("72", "hours"), "at least seventy-two hours' notice")
    assert rules.value_in_sentence("availability_target_percent", "99.95", "at least 99.95% during each period")
    assert rules.value_in_sentence("credit_cap_percent", "99.5", "less than 99.50%, a Service Credit")
    assert rules.value_in_sentence("credit_application", "next_invoice", "applied as a credit against the next invoice",
                                   phrase="against the next invoice")
    assert not rules.value_in_sentence("claim_window", days("61"), "within sixty (60) days")
    assert not rules.value_in_sentence("claim_window", days("5"), "within five (5) business days")
    assert rules.value_in_sentence("claim_window", days("5", "business_days"), "within five (5) Business Days")
    assert not rules.value_in_sentence("maintenance_notice", days("5", "hours"), "5 days' written notice")
    assert not rules.value_in_sentence("credit_cap_percent", "30", "will not exceed twenty-five percent (25%)")
    assert not rules.value_in_sentence("credit_application", "next_invoice", "applied as a credit against the next invoice")
    assert not rules.value_in_sentence("measurement_period", "calendar_month", "the Monthly Fees for that period",
                                       phrase="calendar month")
    assert not rules.value_in_sentence("claim_window", None, "thirty (30) days")


def test_plausibility():
    good = EXPECTED["halcyon-a"]["terms"]
    assert rules.plausibility(good) == []
    assert rules.plausibility(dict(good, availability_target_percent=None)) == []
    tiers = lambda *rows: [{"below_percent": b, "credit_percent": c} for b, c in rows]
    assert any("above the commitment" in p for p in rules.plausibility(dict(good, credit_schedule=tiers(("99.99", "10")))))
    assert any("do not fall as the credits rise" in p
               for p in rules.plausibility(dict(good, credit_schedule=tiers(("99.95", "10"), ("99.5", "5")))))
    assert any("2 different credits" in p
               for p in rules.plausibility(dict(good, credit_schedule=tiers(("99.5", "10"), ("99.5", "25")))))
    assert any("cap" in p for p in rules.plausibility(dict(good, credit_cap_percent="20")))
    assert any("positive" in p for p in rules.plausibility(dict(good, claim_window={"value": "0", "unit": "days"})))
    assert any("positive" in p for p in rules.plausibility(dict(good, maintenance_notice={"value": "2", "unit": "weeks"})))
    assert any("between 0 and 100" in p for p in rules.plausibility(dict(good, credit_cap_percent="130")))


# --- Version 2: readers that differ ------------------------------------------------------------

def test_three_readers_differ_in_instructions_and_model(tmp_path):
    claude = FakeClaude()
    build = engine(tmp_path, claude).start(SAMPLE)
    on_a = {c[1]: c[3] for c in claude.readers("a")}
    assert on_a == {"clause_by_clause": "claude-opus-5-5", "numbers_first": "claude-opus-5-5", "sceptic": "claude-sonnet-5-5"}
    assert {c[1]: c[3] for c in claude.readers("b")} == on_a  # three fresh readers on the second contract
    steps = {s["id"]: s for s in build["steps"]}
    assert [steps["reader-%d" % i]["detail"]["role"] for i in (1, 2, 3)] == ["clause_by_clause", "numbers_first", "sceptic"]
    assert steps["reader-3"]["model"] == "claude-sonnet-5-5" and steps["reader-1"]["model"] == "claude-opus-5-5"
    assert steps["reader-2"]["detail"]["numbers_listed"] == 1 and steps["reader-3"]["detail"]["conflicts"] == []
    prompts = {role: tb.reader_prompt("x", role) for role in ROLES}
    assert len(set(prompts.values())) == 3 and "second place" in prompts["sceptic"] and "every number" in prompts["numbers_first"]


def test_a_sceptic_conflict_puts_the_term_under_review(tmp_path):
    item = reader_item("credit_schedule", EXPECTED["halcyon-a"]["terms"]["credit_schedule"], quote_for("credit_schedule"))
    override = {"credit_schedule": {3: dict(item, conflict="6.2 If Platform Availability falls below 99.5% in any three")}}
    build = engine(tmp_path, FakeClaude(reader_override=override)).start(SAMPLE)
    term = next(t for t in build["terms"] if t["field"] == "credit_schedule")
    assert term["conflict"].startswith("6.2") and term["status"] == "REVIEW"
    assert build["steps"][3]["detail"]["conflicts"][0]["field"] == "credit_schedule"


def test_claude_cli_takes_the_model_per_call_and_verifies_the_envelope(tmp_path):
    fake = tmp_path / "claude"
    fake.write_text("#!/bin/sh\nfor a in \"$@\"; do if [ \"$prev\" = --model ]; then m=$a; fi; prev=$a; done\n"
                    "cat >/dev/null\nif [ \"$m\" = claude-sonnet-5-5 ]; then u=claude-opus-5-5; else u=$m; fi\n"
                    "printf '{\"is_error\": false, \"result\": \"ok\", \"modelUsage\": {\"%s\": {}}}' \"$u\"\n")
    fake.chmod(0o700)
    cli = tb.ClaudeCLI(fake)
    answer = cli("s", "p")
    assert answer == "ok" and answer.model == "claude-opus-5-5"
    with pytest.raises(tb.ModelFailed, match="did not come from claude-sonnet-5-5"):
        cli("s", "p", model="claude-sonnet-5-5")


# --- Version 2: Jev routes the run ---------------------------------------------------------------

def test_jev_matches_an_approved_template_and_no_reader_starts(tmp_path):
    claude, jev = FakeClaude(), FakeJev()
    builds, first = approved(tmp_path, claude, jev)
    calls = len(claude.calls)
    second = builds.start(contract={"title": "Platform Availability Addendum", "vendor": "Halcyon Grid Services",
                                    "text": RAW["c"]}, consent=True)
    assert len(claude.calls) == calls  # the fake Claude was never invoked
    assert second["state"] == "MATCHED" and second["sample_id"] is None and second["source"]["kind"] == "pasted"
    assert second["matched_template"] == {"id": first["template"]["id"], "sha256": first["template"]["sha256"],
                                          "probability": "0.95"}
    steps = {s["id"]: s for s in second["steps"]}
    assert [steps[i]["state"] for i in ("reader-1", "reader-2", "reader-3", "build", "review")] == ["SKIPPED"] * 5
    assert steps["reader-1"]["summary"] == "Not started: Jev matched an approved template"
    assert all(steps[i]["model"] is None for i in ("reader-1", "reader-2", "reader-3", "build"))
    assert steps["classify"]["detail"]["choice"] == first["template"]["id"]
    assert [c["id"] for c in second["checks"]] == ["complete", "unambiguous", "value_in_sentence", "plausible", "template_match"]
    assert all(c["ok"] for c in second["checks"])
    reading = second["readings"][0]
    assert reading["status"] == "ACCEPTED" and reading["model_calls"] == 0
    assert {t["field"]: t["value"] for t in reading["terms"]} == EXPECTED["halcyon-c"]["terms"]
    question, options = jev.calls[-1][1], jev.calls[-1][2]
    assert options[-1] == "unrecognised" and "Halcyon Grid Services" in options[0] and options[0].startswith(first["template"]["id"])
    assert "Platform Availability" in question
    stored = list((tmp_path / "template-builds").glob(second["id"] + "-contract.txt"))
    assert len(stored) == 1 and stat_mode(stored[0]) == 0o600


def test_a_match_under_080_starts_the_readers(tmp_path):
    claude = FakeClaude()
    builds, first = approved(tmp_path, claude, FakeJev())
    builds.jev = FakeJev(choice_probability="0.79")
    calls = len(claude.readers())
    build = builds.start(SAMPLE)
    assert build["state"] == "READY_FOR_REVIEW" and len(claude.readers()) == calls + 6
    assert "under 0.80" in build["steps"][0]["summary"] and build["steps"][0]["detail"]["probability"] == "0.79"
    assert build["template"]["id"] == SAMPLE + "/2"


def test_unrecognised_starts_the_readers(tmp_path):
    claude = FakeClaude()
    builds, first = approved(tmp_path, claude, FakeJev())
    builds.jev = FakeJev(choose=unrecognised)
    build = builds.start(SAMPLE)
    assert build["state"] == "READY_FOR_REVIEW" and build["steps"][0]["detail"]["choice"] == "unrecognised"


def test_with_no_approved_template_jev_is_not_asked(tmp_path):
    jev = FakeJev()
    build = engine(tmp_path, jev=jev).start(SAMPLE)
    classify = build["steps"][0]
    assert classify["state"] == "DONE" and classify["model"] is None and "nothing for Jev to match" in classify["summary"]
    assert classify["detail"] == {"choice": "unrecognised", "probability": None, "options": ["unrecognised"], "asked": False}
    assert not [c for c in jev.calls if c[0] == "choice"] and build["state"] == "READY_FOR_REVIEW"


def test_jev_unreachable_waits_for_a_reviewer_then_builds_with_every_term_flagged(served, tmp_path):
    claude = FakeClaude()
    builds, first = approved(tmp_path, claude)
    builds.jev = FakeJev(unreachable=True)
    claude.calls.clear()
    app, client, actor, _ = served
    app.state.template_builds = builds
    started = actor.post("/api/template-builds", {"sample_id": SAMPLE})
    assert started.status_code == 202, started.text
    build = started.json()["build"]
    assert build["state"] == "NEEDS_REVIEWER" and claude.calls == []  # nothing started
    assert build["steps"][0]["state"] == "FAILED" and "Jev could not be reached" in build["steps"][0]["summary"]
    assert [s["state"] for s in build["steps"][1:]] == ["PENDING"] * 6
    early = actor.post(f"/api/template-builds/{build['id']}/approve", {"template_sha256": "0" * 64})
    assert early.status_code == 409
    went = actor.post(f"/api/template-builds/{build['id']}/continue", {})
    assert went.status_code == 200, went.text
    build = went.json()["build"]
    assert build["state"] == "READY_FOR_REVIEW" and len(claude.readers()) == 6
    decision = build["steps"][0]["detail"]["reviewer_decision"]
    assert set(decision) == {"by", "at"} and decision["by"] == SCRIPT and decision["at"].endswith("Z")
    ran = [s for s in build["steps"][1:6]]
    assert all(s["started_at"] >= decision["at"] and s["finished_at"] and s["seconds"] for s in ran)
    assert all(t["jev"] is None and t["needs_acknowledgement"] for t in build["terms"])
    jev = check(build, "jev")
    assert jev["ran"] is False and jev["ok"] is False and jev["lowest"] is None and len(jev["needs_acknowledgement"]) == 7
    assert actor.post(f"/api/template-builds/{build['id']}/continue", {}).status_code == 409
    refused = actor.post(f"/api/template-builds/{build['id']}/approve",
                         {"template_sha256": build["template"]["sha256"], "acknowledged": []})
    assert refused.status_code == 409 and "acknowledge exactly" in refused.json()["detail"]
    every = [t["field"] for t in build["terms"]]
    done = actor.post(f"/api/template-builds/{build['id']}/approve",
                      {"template_sha256": build["template"]["sha256"], "acknowledged": every})
    assert done.status_code == 200, done.text
    review = done.json()["build"]["steps"][-1]["detail"]
    assert review["acknowledged"] == every and review["without_jev"] is True


# --- Version 2: Jev per term gates approval ------------------------------------------------------

def test_approval_is_refused_until_the_flagged_terms_are_acknowledged(tmp_path):
    builds = engine(tmp_path, jev=FakeJev(no=("limit the total service credits",), low=("notice before scheduled maintenance",)))
    build = builds.start(SAMPLE)
    flagged = sorted(t["field"] for t in build["terms"] if t["needs_acknowledgement"])
    assert flagged == ["credit_cap_percent", "maintenance_notice"]
    assert sorted(check(build, "jev")["needs_acknowledgement"]) == flagged and build["state"] == "READY_FOR_REVIEW"
    sha = build["template"]["sha256"]
    for wrong in ([], ["credit_cap_percent"], flagged + ["claim_window"], flagged + ["credit_cap_percent"]):
        with pytest.raises(TemplateRefused, match="acknowledge exactly"):
            builds.approve(build["id"], sha, "reviewer", wrong)
    assert builds.get(build["id"])["state"] == "READY_FOR_REVIEW"
    done = builds.approve(build["id"], sha, "reviewer", list(reversed(flagged)))
    assert done["state"] == "APPROVED" and sorted(done["steps"][-1]["detail"]["acknowledged"]) == flagged


def test_a_term_jev_did_not_answer_needs_acknowledgement(tmp_path):
    class Silent(FakeJev):
        def yes_no(self, question, context):
            if "claim" in question:
                raise ConnectionError("dropped")
            return super().yes_no(question, context)
    build = engine(tmp_path, jev=Silent()).start(SAMPLE)
    flagged = [t["field"] for t in build["terms"] if t["needs_acknowledgement"]]
    assert flagged == ["claim_window"] and check(build, "jev")["ran"] is True


# --- Version 2: the keyless second-contract check ---------------------------------------------------

def test_second_contract_check_passes_against_what_its_readers_agreed(tmp_path):
    build = engine(tmp_path).start(SAMPLE)
    second = check(build, "second_document")
    assert second["ok"] and second["ran"] and second["blocking"] and second["passed"] == 7
    assert [r["role"] for r in second["readers"]] == ["clause_by_clause", "numbers_first", "sceptic"]
    assert "no answer key" in second["basis"]
    claim = next(t for t in build["terms"] if t["field"] == "claim_window")
    assert claim["second_readers"] == {"agree": 3, "of": 3, "value": {"value": "45", "unit": "days"}, "stated": True}
    assert claim["second_document_value"] == {"value": "45", "unit": "days"}


def test_second_contract_check_fails_when_its_readers_agree_on_another_value(tmp_path):
    sentence = quote_for("claim_window", RAW["b"])
    other = {"claim_window": {1: {"value": "46", "unit": "days", "quote": sentence}, 2: {"value": "46", "unit": "days", "quote": sentence}}}
    claude = FakeClaude(second_override=other)
    builds = engine(tmp_path, claude)
    build = builds.start(SAMPLE)
    second = check(build, "second_document")
    assert second["ok"] is False and second["passed"] == 6 and second["blocking"] is True
    claim = next(t for t in build["terms"] if t["field"] == "claim_window")
    assert claim["second_readers"]["value"] == {"value": "46", "unit": "days"} and claim["second_document_ok"] is False
    assert [c[0] for c in claude.calls].count("repair") == 2
    with pytest.raises(TemplateRefused, match="blocking check"):
        builds.approve(build["id"], build["template"]["sha256"], "reviewer", [])


def test_second_contract_readers_without_a_majority_fail_the_term(tmp_path):
    sentence = quote_for("credit_cap_percent", RAW["b"])
    split = {"credit_cap_percent": {1: {"value": "26", "quote": sentence}, 2: {"value": "27", "quote": sentence}}}
    build = engine(tmp_path, FakeClaude(second_override=split)).start(SAMPLE)
    cap = next(t for t in build["terms"] if t["field"] == "credit_cap_percent")
    assert cap["second_readers"]["value"] is None and cap["second_document_ok"] is False
    assert check(build, "second_document")["ok"] is False


# --- Version 2: a pasted contract ------------------------------------------------------------------

def test_a_pasted_contract_without_consent_is_refused(served, tmp_path):
    builds = engine(tmp_path)
    contract = {"title": "Addendum", "vendor": "Halcyon Grid Services", "text": RAW["a"]}
    for consent in (False, None, "yes"):
        with pytest.raises(TemplateRefused, match="consent") as refused:
            builds.start(contract=contract, consent=consent)
        assert refused.value.status == 400
    with pytest.raises(TemplateRefused, match="longer than 60,000"):
        builds.start(contract=dict(contract, text="x" * 60_001), consent=True)
    with pytest.raises(TemplateRefused, match="either a sample or a pasted contract"):
        builds.start(SAMPLE, contract=contract, consent=True)
    assert builds.builds == {} and list((tmp_path / "template-builds").iterdir()) == []
    app, client, actor, _ = served
    app.state.template_builds = builds
    short = dict(contract, text=RAW["a"][:2000])  # signed bodies over 4,096 bytes stop at uptime/server.py (413)
    answer = actor.post("/api/template-builds", {"contract": short, "second_contract": None})
    assert answer.status_code == 400 and "consent" in answer.json()["detail"]


def test_a_pasted_contract_with_a_second_contract_builds_like_a_sample(tmp_path):
    builds = engine(tmp_path)
    build = builds.start(contract={"title": "Platform  Availability Addendum", "vendor": "Halcyon Grid Services",
                                   "text": RAW["a"]},
                         second_contract={"title": "Larkspur addendum", "text": RAW["b"]}, consent=True)
    assert build["state"] == "READY_FOR_REVIEW" and build["sample_id"] is None
    assert build["source"] == {"kind": "pasted", "title": "Platform Availability Addendum",
                               "vendor": "Halcyon Grid Services", "chars": len(RAW["a"])}
    assert build["second"] == {"provided": True, "title": "Larkspur addendum"}
    assert all(c["ok"] for c in build["checks"]) and build["template"]["id"] == "halcyon-grid-services-platform-availability-addendum/1"
    folder = tmp_path / "template-builds"
    for name in (build["id"] + "-contract.txt", build["id"] + "-second.txt", build["id"] + ".json"):
        assert stat_mode(folder / name) == 0o600
    assert stat_mode(folder) == 0o700
    template = next(t for t in builds.overview()["templates"] if t["id"] == build["template"]["id"])
    assert template["sample_id"] is None and template["vendor"] == "Halcyon Grid Services"


def test_a_pasted_contract_without_a_second_contract_can_be_approved_unchecked(tmp_path):
    builds = engine(tmp_path)
    build = builds.start(contract={"title": "Addendum", "vendor": "Halcyon Grid Services", "text": RAW["a"]}, consent=True)
    second = check(build, "second_document")
    assert second == {"id": "second_document", "label": "The template reads a second contract of the same form",
                      "passed": 0, "total": 0, "blocking": False, "by": "UPTIME", "ran": False, "document": None,
                      "readers": [], "basis": "No second contract was given, so this was not checked.", "ok": False,
                      "not_stated": 0}
    assert build["second"] == {"provided": False, "title": None}
    assert all(t["second_readers"] is None for t in build["terms"])
    assert builds.approve(build["id"], build["template"]["sha256"], "reviewer", [])["state"] == "APPROVED"


def test_the_build_limit_is_twelve(tmp_path):
    assert tb.MAX_BUILDS == 12
    builds = TemplateBuilds(tmp_path / "tb", FakeClaude(), FakeJev(unreachable=True), background=False)
    contract = {"title": "Addendum", "vendor": "Halcyon Grid Services", "text": RAW["a"]}
    for _ in range(12):
        builds.start(contract=contract, consent=True)
    with pytest.raises(TemplateRefused, match="12 template builds") as refused:
        builds.start(contract=contract, consent=True)
    assert refused.value.status == 429


# --- Version 2: guarded reads ---------------------------------------------------------------------

def read_text(builds, build, text):
    return builds.read(build["id"], document={"title": "Next addendum", "text": text})


def test_a_read_of_an_ambiguous_contract_is_refused(tmp_path):
    builds, build = approved(tmp_path)
    twice = edited("6.3 This Addendum", "6.3 Halcyon will make the Covered Services available with a Platform "
                   "Availability of at least 99.9% during each Measurement Period. 6.4 This Addendum")
    reading = read_text(builds, build, twice)
    assert reading["status"] == "REFUSED" and guard(reading, "unambiguous")["ok"] is False
    assert "matched in 2 places" in guard(reading, "unambiguous")["detail"]
    term = next(t for t in reading["terms"] if t["field"] == "availability_target_percent")
    assert term["value"] is None and term["display"] is None and "different values" in term["error"]
    assert any(r.startswith("No rule matched in two places") for r in reading["reasons"])


def test_a_read_missing_a_term_is_refused(tmp_path):
    builds, build = approved(tmp_path)
    reading = read_text(builds, build, edited("will not exceed thirty percent (30%)", "is unlimited"))
    assert reading["status"] == "REFUSED" and guard(reading, "complete") == {
        "id": "complete", "ok": False, "detail": "6 of 7", "label": "Every rule found a value"}
    assert guard(reading, "unambiguous")["ok"] and guard(reading, "plausible")["ok"]


def test_a_read_whose_value_is_not_in_its_sentence_is_refused(tmp_path):
    loose = dict(GOOD_RULES, credit_application={
        "pattern": r"Service Credits will be applied as a credit (against the next \w+)",
        "map": {"against the next invoice": "next_invoice", "against the next statement": "next_invoice"}})
    builds, build = approved(tmp_path, FakeClaude(builder_rules=loose))
    reading = read_text(builds, build, edited("applied as a credit against the next invoice",
                                              "applied as a credit against the next statement"))
    # The builder's extra map entry ("against the next statement") was given by no reader, so it is not in the
    # approved template's map: the read finds no value for the term and is refused, as before, now by `complete`.
    assert reading["status"] == "REFUSED" and guard(reading, "complete")["ok"] is False
    assert guard(reading, "complete")["detail"] == "6 of 7" and guard(reading, "value_in_sentence")["ok"]
    rule = next(r for r in builds.builds[build["id"]]["_template_body"]["rules"] if r["field"] == "credit_application")
    assert rule["map"] == {"against the next invoice": "next_invoice"}


def test_an_implausible_read_is_refused(tmp_path):
    builds, build = approved(tmp_path)
    reading = read_text(builds, build, edited("will not exceed thirty percent (30%)", "will not exceed twenty percent (20%)"))
    assert reading["status"] == "REFUSED" and guard(reading, "plausible")["ok"] is False
    assert "below the highest credit" in guard(reading, "plausible")["detail"]
    assert all(guard(reading, g)["ok"] for g in ("complete", "unambiguous", "value_in_sentence", "template_match"))
    # A schedule whose credit does not rise as the threshold falls is refused by the interpreter itself.
    falling = read_text(builds, build, edited("a Service Credit of 25% of the Monthly Fees", "a Service Credit of 5% of the Monthly Fees"))
    schedule = next(t for t in falling["terms"] if t["field"] == "credit_schedule")
    assert falling["status"] == "REFUSED" and schedule["value"] is None and "do not fall as the credits rise" in schedule["error"]


def test_a_read_jev_does_not_match_to_the_template_is_refused(tmp_path):
    builds, build = approved(tmp_path)
    builds.jev = FakeJev(choose=unrecognised)
    reading = builds.read(build["id"], document_id="halcyon-c")
    assert reading["status"] == "REFUSED" and guard(reading, "template_match")["ok"] is False
    assert guard(reading, "template_match")["advisory"] is False and reading["jev_template"]["choice"] == "unrecognised"
    builds.jev = FakeJev(choice_probability="0.6")
    low = builds.read(build["id"], document_id="halcyon-c")
    assert low["status"] == "REFUSED" and "0.6" in guard(low, "template_match")["detail"]


def test_with_jev_unreachable_the_template_match_guard_is_advisory(tmp_path):
    builds, build = approved(tmp_path)
    builds.jev = FakeJev(unreachable=True)
    reading = builds.read(build["id"], document_id="halcyon-c")
    match = guard(reading, "template_match")
    assert reading["status"] == "ACCEPTED" and match["ok"] is False and match["advisory"] is True
    assert "could not be reached" in match["detail"] and reading["jev_template"] is None


def test_read_takes_a_document_id_or_a_pasted_document(served, tmp_path):
    builds, build = approved(tmp_path)
    with pytest.raises(TemplateRefused):
        builds.read(build["id"])
    with pytest.raises(TemplateRefused):
        builds.read(build["id"], "halcyon-c", {"title": "x", "text": "y"})
    pasted = read_text(builds, build, RAW["c"])
    assert pasted["status"] == "ACCEPTED" and pasted["document"]["id"] == "pasted-" + pasted["id"]
    assert pasted["document"]["vendor"] == "Halcyon Grid Services" and pasted["document"]["customer"] is None
    app, client, actor, _ = served
    app.state.template_builds = builds
    short = RAW["c"][:2500]  # signed bodies over 4,096 bytes stop at uptime/server.py (413)
    contract = {"title": "Next", "vendor": "Halcyon Grid Services", "text": short}
    refused = actor.post(f"/api/template-builds/{build['id']}/read", {"contract": contract})
    assert refused.status_code == 400 and "consent" in refused.json()["detail"]
    both = actor.post(f"/api/template-builds/{build['id']}/read", {"document_id": "halcyon-c", "contract": contract})
    assert both.status_code == 400
    part = actor.post(f"/api/template-builds/{build['id']}/read", {"contract": contract, "consent": True})
    assert part.status_code == 200 and part.json()["reading"]["status"] == "REFUSED"
    assert guard(part.json()["reading"], "complete")["ok"] is False
    assert len(builds.get(build["id"])["readings"]) == 2


# --- Version 2: for the money link --------------------------------------------------------------

def test_on_reading_attaches_an_agreement_and_approved_readings_lists_it(tmp_path):
    builds, build = approved(tmp_path)
    seen = []

    def link(entry):
        seen.append(entry)
        return {"agreement_id": "HGS-PAA-TEST", "state": "SHADOW", "credit": None, "evaluation": "Needs usage evidence"}
    builds.on_reading = link
    reading = builds.read(build["id"], document_id="halcyon-c")
    assert reading["agreement"]["agreement_id"] == "HGS-PAA-TEST"
    entry = seen[0]
    assert set(entry) == {"build_id", "reading_id", "template", "vendor", "document", "values", "read_at"}
    assert entry["build_id"] == build["id"] and entry["reading_id"] == reading["id"]
    assert entry["template"] == {"id": build["template"]["id"], "sha256": build["template"]["sha256"]}
    assert entry["vendor"] == "Halcyon Grid Services"
    assert entry["document"] == {"id": "halcyon-c", "title": reading["document"]["title"], "customer": "Brightwater Freight Co."}
    assert entry["values"] == EXPECTED["halcyon-c"]["terms"]
    assert builds.approved_readings() == [entry]
    stored = json.loads((tmp_path / "template-builds" / (build["id"] + ".json")).read_text())
    assert stored["readings"][0]["agreement"]["agreement_id"] == "HGS-PAA-TEST"
    builds.jev = FakeJev(choose=unrecognised)
    refused = builds.read(build["id"], document_id="halcyon-c")
    assert refused["status"] == "REFUSED" and refused["agreement"] is None and len(seen) == 1
    assert [e["reading_id"] for e in builds.approved_readings()] == [reading["id"]]


def test_on_reading_that_raises_leaves_no_agreement_and_says_so(tmp_path):
    builds, build = approved(tmp_path)

    def broken(entry):
        raise ValueError("no usage")
    builds.on_reading = broken
    reading = builds.read(build["id"], document_id="halcyon-c")
    assert reading["status"] == "ACCEPTED" and reading["agreement"] is None
    assert reading["agreement_note"].startswith("No agreement was created")
    attached = builds.set_agreement(build["id"], reading["id"], {"agreement_id": "LATER", "credit": None})
    assert attached["agreement"] == {"agreement_id": "LATER", "credit": None}
    assert builds.get(build["id"])["readings"][0]["agreement"]["agreement_id"] == "LATER"
    with pytest.raises(TemplateRefused):
        builds.set_agreement(build["id"], "rd_missing", {})


def test_a_matched_build_reading_reaches_the_money_link(tmp_path):
    builds, first = approved(tmp_path)
    builds.on_reading = lambda entry: {"agreement_id": "M-" + entry["document"]["id"], "credit": None}
    matched = builds.start(contract={"title": "Addendum", "vendor": "Halcyon Grid Services", "text": RAW["c"]}, consent=True)
    assert matched["state"] == "MATCHED"
    assert matched["readings"][0]["agreement"] == {"agreement_id": "M-" + matched["id"] + "-contract", "credit": None}
    listed = builds.approved_readings()
    assert [e["build_id"] for e in listed] == [matched["id"]] and listed[0]["template"]["id"] == first["template"]["id"]


# --- After the held-out baseline -------------------------------------------------------------------

def test_a_choice_map_naming_an_unknown_option_fails_and_is_repaired(tmp_path):
    bad = dict(GOOD_RULES, credit_application={
        "pattern": GOOD_RULES["credit_application"]["pattern"], "map": {"against the next invoice": "account_credit"}})
    claude = FakeClaude(builder_rules=bad)
    build = engine(tmp_path, claude).start(SAMPLE)
    assert [c[0] for c in claude.calls].count("repair") == 1 and check(build, "reproduce")["ok"]
    found = rules.run_rule({"field": "credit_application", **bad["credit_application"]}, TEXT_A)
    assert found["value"] is None and "account_credit, which is not an option" in found["error"]


def test_a_wrong_shaped_repair_answer_uses_a_round_and_the_next_round_runs(tmp_path):
    hardwired = dict(GOOD_RULES, claim_window={"pattern": r"within (?P<value>thirty) \(\d+\) (?P<unit>days) after the end"})

    class Flaky(FakeClaude):
        def __call__(self, system, prompt, model=None):
            if prompt.startswith("Some extraction rules") and not any(c[0] == "repair" for c in self.calls):
                self.calls.append(("repair", None, None, model))
                return "not json"
            return super().__call__(system, prompt, model)
    claude = Flaky(builder_rules=hardwired)
    build = engine(tmp_path, claude).start(SAMPLE)
    detail = build["steps"][4]["detail"]
    assert detail["repair_rounds"] == 2 and "Repair round 1 failed" in detail["repair_note"]
    assert check(build, "second_document")["ok"] and build["state"] == "READY_FOR_REVIEW"


def test_every_reading_term_says_why_it_is_blank(tmp_path):
    builds, build = approved(tmp_path)
    twice = edited("6.3 This Addendum", "6.3 Platform Availability of at least 99.9% applies to the Beta tier. 6.4 This Addendum",
                   edited("will not exceed thirty percent (30%)", "is unlimited"))
    reading = read_text(builds, build, twice)
    terms = {t["field"]: t for t in reading["terms"]}
    assert terms["credit_cap_percent"]["failed_guards"] == ["complete"] and "found nothing" in terms["credit_cap_percent"]["error"]
    assert terms["availability_target_percent"]["failed_guards"] == ["complete", "unambiguous"]
    assert "2 places" in terms["availability_target_percent"]["error"]
    assert terms["claim_window"]["failed_guards"] == [] and terms["claim_window"]["error"] is None


def test_jev_questions_ask_what_the_sentence_literally_says(tmp_path):
    jev = FakeJev()
    engine(tmp_path, jev=jev).start(SAMPLE)
    asked = [c[1] for c in jev.calls if c[0] == "yes_no"]
    assert "Does this sentence give a service credit of 25% of the fees when availability is below 99.5%?" in asked
    assert "Does this sentence give a service credit of 10% of the fees when availability is below 99.95%?" in asked
    # once per stated term, and once per tier of the schedule: 6 terms + 2 tiers
    assert all(q.startswith("Does this sentence") and q.endswith("?") and len(q) <= 1000 for q in asked) and len(asked) == 8


# --- A term every reader agrees the contract does not state ---------------------------------------

DAYS = {"value": None, "quote": None, "stated": False, "reason": "5 days' written notice"}


def silent(field, readers=(1, 2, 3), item=DAYS):
    return {field: {i: dict(item) for i in readers}}


def test_a_term_all_readers_say_is_not_stated_is_approvable_once_acknowledged(tmp_path):
    claude = FakeClaude(reader_override=silent("maintenance_notice"),
                        second_override=silent("maintenance_notice"))
    builds = engine(tmp_path, claude)
    build = builds.start(SAMPLE)
    term = next(t for t in build["terms"] if t["field"] == "maintenance_notice")
    assert {k: term[k] for k in ("status", "stated", "value", "display", "quote", "reason", "rule", "jev",
                                 "needs_acknowledgement")} == {
        "status": "NOT_STATED", "stated": False, "value": None, "display": None, "quote": None,
        "reason": "5 days' written notice", "rule": None, "jev": None, "needs_acknowledgement": True}
    assert term["second_document_ok"] is True and term["second_readers"]["stated"] is False
    assert all(t["stated"] for t in build["terms"] if t["field"] != "maintenance_notice")
    assert all(c["not_stated"] == 1 for c in build["checks"])
    assert check(build, "value_in_sentence")["total"] == 6 and check(build, "reproduce")["total"] == 6
    assert check(build, "jev")["total"] == 6 and check(build, "second_document")["total"] == 7
    assert all(c["ok"] for c in build["checks"] if c["blocking"]), build["checks"]
    builder = next(p for p in claude.prompts if p.startswith("Write one extraction rule"))
    assert "maintenance_notice" not in builder.split("with exactly these fields:")[1].split(".")[0]
    body = builds.builds[build["id"]]["_template_body"]
    assert body["not_stated"] == ["maintenance_notice"] and len(body["rules"]) == 6
    assert build["template"]["rules"] == 6 and build["template"]["not_stated"] == ["maintenance_notice"]
    assert rules.sha256(body) == build["template"]["sha256"]
    assert not [c for c in builds.jev.calls if c[0] == "yes_no" and "maintenance" in c[1]]
    sha = build["template"]["sha256"]
    with pytest.raises(TemplateRefused, match="acknowledge exactly"):
        builds.approve(build["id"], sha, "reviewer", [])
    done = builds.approve(build["id"], sha, "reviewer", ["maintenance_notice"])
    assert done["state"] == "APPROVED" and done["steps"][-1]["detail"]["acknowledged"] == ["maintenance_notice"]

    # A read reports the not-stated field without failing `complete`.
    builds.on_reading = lambda entry: {"values": entry["values"]}
    reading = builds.read(build["id"], document_id="halcyon-c")
    assert reading["status"] == "ACCEPTED" and guard(reading, "complete")["ok"]
    assert reading["found"] == reading["total"] == 6 and reading["not_stated"] == ["maintenance_notice"]
    assert guard(reading, "complete")["detail"] == "6 of 6" and guard(reading, "unambiguous")["ok"]
    notice = next(t for t in reading["terms"] if t["field"] == "maintenance_notice")
    assert {k: notice[k] for k in ("value", "display", "quote", "stated", "error")} == {
        "value": None, "display": None, "quote": None, "stated": False,
        "error": "Not stated in the contract this template was built from"}
    assert notice["failed_guards"] == []
    entry = builds.approved_readings()[0]
    assert entry["values"]["maintenance_notice"] is None and entry["values"]["claim_window"] == {"value": "60", "unit": "days"}
    assert reading["agreement"]["values"]["maintenance_notice"] is None


def test_a_reader_converting_days_to_hours_is_caught_by_value_in_sentence(tmp_path):
    sentence = quote_for("maintenance_notice")  # states seventy-two (72) hours
    converted = {"maintenance_notice": {1: {"value": "120", "unit": "hours", "quote": sentence},
                                        2: {"value": "120", "unit": "hours", "quote": sentence}}}
    builds = engine(tmp_path, FakeClaude(reader_override=converted))
    build = builds.start(SAMPLE)
    term = next(t for t in build["terms"] if t["field"] == "maintenance_notice")
    assert term["stated"] is True and term["value"] == {"value": "120", "unit": "hours"} and term["value_in_sentence"] is False
    assert term["status"] == "REVIEW" and check(build, "value_in_sentence")["ok"] is False
    assert check(build, "reproduce")["ok"] is False
    with pytest.raises(TemplateRefused, match="blocking check"):
        builds.approve(build["id"], build["template"]["sha256"], "reviewer",
                       [t["field"] for t in build["terms"] if t["needs_acknowledgement"]])


def test_readers_disagreeing_on_whether_a_term_is_stated_invent_no_value(tmp_path):
    mixed = silent("maintenance_notice", readers=(1, 2))
    build = engine(tmp_path, FakeClaude(reader_override=mixed)).start(SAMPLE)
    term = next(t for t in build["terms"] if t["field"] == "maintenance_notice")
    assert term["stated"] is True and term["status"] == "REVIEW" and term["value"] is None
    assert term["agreement"] == {"agree": 2, "of": 3}
    assert check(build, "value_in_sentence")["ok"] is False and check(build, "reproduce")["ok"] is False


def test_a_required_term_not_stated_blocks_approval(tmp_path):
    item = {"value": None, "quote": None, "stated": False, "reason": "Credits are a fixed fee, not a percentage."}
    claude = FakeClaude(reader_override=silent("credit_schedule", item=item),
                        second_override=silent("credit_schedule", item=item))
    builds = engine(tmp_path, claude)
    build = builds.start(SAMPLE)
    stated = check(build, "stated")
    assert stated["ok"] is False and stated["passed"] == 1 and stated["total"] == 2 and stated["blocking"] is True
    assert stated["required"] == ["availability_target_percent", "credit_schedule"]
    assert next(t for t in build["terms"] if t["field"] == "credit_schedule")["status"] == "NOT_STATED"
    with pytest.raises(TemplateRefused, match="blocking check failed.*credit needs"):
        builds.approve(build["id"], build["template"]["sha256"], "reviewer",
                       [t["field"] for t in build["terms"] if t["needs_acknowledgement"]])


def test_the_second_contract_stating_a_term_the_first_does_not_fails_second_document(tmp_path):
    build = engine(tmp_path, FakeClaude(reader_override=silent("maintenance_notice"))).start(SAMPLE)
    term = next(t for t in build["terms"] if t["field"] == "maintenance_notice")
    assert term["status"] == "NOT_STATED" and term["second_readers"]["stated"] is True
    assert term["second_document_ok"] is False
    second = check(build, "second_document")
    assert second["ok"] is False and second["passed"] == 6 and second["total"] == 7 and second["not_stated"] == 1


def test_a_reader_saying_not_stated_with_a_value_is_refused():
    with pytest.raises(tb.ModelFailed, match="not stated but gave a value"):
        bad = {f: reader_item(f, v, ["q"] * len(v) if isinstance(v, list) else "q")
               for f, v in EXPECTED["halcyon-a"]["terms"].items()}
        bad["maintenance_notice"] = {"value": "72", "unit": "hours", "quote": "q", "stated": False, "reason": "x"}
        tb.parse_reader(json.dumps({"terms": bad}))
    prompt = tb.reader_prompt("x", "sceptic")
    assert "Never convert between units" in prompt and '{"value": "5", "unit": "business_days"}' in prompt


def test_the_interpreter_skips_not_stated_fields():
    body = {"rules": [{"field": f, "type": rules.TERM[f]["type"], **r} for f, r in GOOD_RULES.items()
                      if f != "credit_cap_percent"], "not_stated": ["credit_cap_percent"]}
    out = rules.apply(body, RAW["a"])
    cap = next(t for t in out["terms"] if t["field"] == "credit_cap_percent")
    assert out["found"] == out["total"] == 6 and out["not_stated"] == ["credit_cap_percent"]
    assert cap["stated"] is False and cap["value"] is None and cap["error"] == rules.NOT_STATED
    assert rules.plausibility({t["field"]: t["value"] for t in out["terms"]}) == []


# --- Version 3: a credit schedule of one to six tiers, and durations with units --------------------

def tiers(*rows):
    return [{"below_percent": b, "credit_percent": c} for b, c in rows]


def schedule(text, *row_rules, commitment=None):
    norm, lines = rules.normalize_lines(text)
    return rules.run_rule({"field": "credit_schedule", "rows": list(row_rules)}, norm, lines=lines, commitment=commitment)


TABLE = ("Monthly Uptime Percentage | Service Credit Percentage\n"
         "Less than 99.99% but equal to or greater than 99.0% | 10%\n"
         "Less than 99.0% but equal to or greater than 95.0% | 30%\n"
         "Less than 95.0% | 100%\n")
ROW = {"pattern": r"Less than (?P<below>\d+(?:\.\d+)?)%[^|]*\| (?P<credit>\d+(?:\.\d+)?)%"}


def test_normalize_lines_matches_normalize_and_keeps_line_numbers():
    text = "  A  b\n\n c\td \r\n e “f”  \n"
    norm, lines = rules.normalize_lines(text)
    assert norm == rules.normalize(text) and len(lines) == len(norm)
    assert lines[norm.index("A")] == 0 and lines[norm.index("c")] == 2 and lines[norm.index("e")] == 3


def test_a_table_of_three_tiers_reads_one_row_per_line():
    found = schedule(TABLE, ROW)
    assert found["error"] is None and found["places"] == 3
    assert found["value"] == tiers(("99.99", "10"), ("99", "30"), ("95", "100"))
    assert found["quote"] == ["Less than 99.99% but equal to or greater than 99.0% | 10%",
                              "Less than 99.0% but equal to or greater than 95.0% | 30%", "Less than 95.0% | 100%"]
    assert rules.display("credit_schedule", found["value"]) == "below 99.99%: 10%; below 99%: 30%; below 95%: 100%"
    assert rules.value_in_sentence("credit_schedule", found["value"], found["quote"])
    # Without the line structure the whole table is one sentence, so three different tiers in it read nothing.
    flat = rules.run_rule({"field": "credit_schedule", "rows": [ROW]}, rules.normalize(TABLE))
    assert flat["value"] is None and flat["ambiguous"] and "one sentence or line" in flat["error"]


def test_a_single_flat_credit_is_a_schedule_of_one():
    text = "If the Monthly Uptime falls below 99.9%, Customer will receive a credit of 10% of the monthly fee."
    found = schedule(text, {"pattern": r"falls below (?P<below>[\d.]+)%, Customer will receive a credit of (?P<credit>[\d.]+)%"})
    assert found["value"] == tiers(("99.9", "10")) and found["quote"] == [rules.normalize(text)]


def test_a_tier_whose_threshold_is_the_commitment_itself():
    text = ("7.1 If Availability is below the Availability Commitment but equal to or above 98.75 per cent, a rebate of "
            "seven and a half per cent (7.5%) applies.\n7.2 If Availability is below 98.75 per cent, a rebate of twenty "
            "per cent (20%) applies.")
    first = {"pattern": r"below the Availability Commitment[^;]*?\((?P<credit>[\d.]+)%\)", "below": "commitment"}
    second = {"pattern": r"7\.2 If Availability is below (?P<below>[\d.]+) per cent, a rebate of [a-z ]+\((?P<credit>[\d.]+)%\)"}
    found = schedule(text, first, second, commitment="99.5")
    assert found["value"] == tiers(("99.5", "7.5"), ("98.75", "20"))
    assert rules.value_in_sentence("credit_schedule", found["value"], found["quote"], commitment="99.5")
    assert not rules.value_in_sentence("credit_schedule", found["value"], found["quote"], commitment="99.9")
    assert "was not read" in schedule(text, first, second)["error"]
    assert 'may only be "commitment"' in schedule(text, dict(first, below="99.5"))["error"]


@pytest.mark.parametrize("table, error", [
    ("Less than 99.9% | 10%\nLess than 99.9% | 25%\n", "2 different credits (10%, 25%) for availability below 99.9%"),
    ("Less than 99.9% | 25%\nLess than 99.0% | 10%\n", "do not fall as the credits rise"),
    ("".join("Less than %d%% | %d%%\n" % (99 - i, 10 + i) for i in range(7)), "7 tiers; at most 6"),
])
def test_a_schedule_that_does_not_fit_together_reads_nothing(table, error):
    found = schedule(table, ROW)
    assert found["value"] is None and error in found["error"]


def test_identical_tiers_in_two_places_are_one_tier():
    text = TABLE + "As stated above: Less than 95.0% | 100%\n"
    assert schedule(text, ROW)["value"] == tiers(("99.99", "10"), ("99", "30"), ("95", "100"))


def test_a_schedule_rule_shape_is_checked():
    assert "named groups" in schedule(TABLE, {"pattern": r"Less than (\d+)%"})["error"]
    assert "one to 6 row patterns" in schedule(TABLE)["error"]
    assert "spells out" in schedule(TABLE, {"pattern": r"Less than (?P<below>95\.0)% \| (?P<credit>\d+)%"})["error"]
    with pytest.raises(tb.ModelFailed, match="schedule rule"):
        tb.parse_rules(json.dumps({"rules": {"credit_schedule": {"pattern": "x"}}}), ["credit_schedule"])
    parsed = tb.parse_rules(json.dumps({"rules": {"credit_schedule": {"rows": [ROW, dict(ROW, below="commitment")]}}}),
                            ["credit_schedule"])
    assert parsed["credit_schedule"] == {"field": "credit_schedule", "type": "schedule",
                                         "rows": [ROW, dict(ROW, below="commitment")]}


def test_durations_keep_the_contracts_unit():
    text = "Customer must submit a claim within ten (10) Business Days. Vendor gives at least 5 days' notice."
    claim = rules.run_rule({"field": "claim_window", "pattern": r"claim within [a-z]+ \((?P<value>\d+)\) (?P<unit>business days|days)"},
                           rules.normalize(text))
    assert claim["value"] == {"value": "10", "unit": "business_days"} and rules.display("claim_window", claim["value"]) == "10 business days"
    notice = rules.run_rule({"field": "maintenance_notice", "pattern": r"at least (?P<value>\d+) (?P<unit>hours|days)'"},
                            rules.normalize(text))
    assert notice["value"] == {"value": "5", "unit": "days"}  # never 120 hours
    weeks = rules.run_rule({"field": "maintenance_notice", "pattern": r"at least (?P<value>\d+) (?P<unit>weeks)"},
                           "Vendor gives at least 2 weeks notice.")
    assert weeks["value"] is None and "not a duration" in weeks["error"]
    months = rules.run_rule({"field": "maintenance_notice", "pattern": r"(?P<value>\d+) (?P<unit>months)"}, "within 2 months")
    assert months["value"] is None  # months is not a unit of the maintenance notice
    assert rules.canonical_duration("claim_window", "two", "Calendar Months") == {"value": "2", "unit": "months"}
    assert rules.canonical_duration("claim_window", "30", "working days") is None


def test_a_reader_schedule_is_parsed_ordered_and_quoted_per_tier():
    terms = {f: reader_item(f, v, ["q"] * len(v) if isinstance(v, list) else "q") for f, v in EXPECTED["halcyon-a"]["terms"].items()}
    terms["credit_schedule"] = {"value": [{"below": "99.5", "credit": "25", "quote": "(b) lower"},
                                          {"below": "commitment", "credit": "10", "quote": "(a) upper"}], "quote": None}
    found, _ = tb.parse_reader(json.dumps({"terms": terms}))
    assert found["credit_schedule"]["value"] == tiers(("99.95", "10"), ("99.5", "25"))
    assert found["credit_schedule"]["quote"] == ["(a) upper", "(b) lower"]
    assert found["claim_window"]["value"] == {"value": "30", "unit": "days"}
    terms["credit_schedule"]["value"][0]["credit"] = "5"  # credits no longer rise as thresholds fall
    found, _ = tb.parse_reader(json.dumps({"terms": terms}))
    assert found["credit_schedule"]["value"] is None and found["credit_schedule"]["invalid"] is True
    terms["claim_window"] = {"value": "30", "unit": "weeks", "quote": "q"}
    found, _ = tb.parse_reader(json.dumps({"terms": terms}))
    assert found["claim_window"]["value"] is None and found["claim_window"]["invalid"] is True


def test_readers_must_agree_on_the_whole_schedule_and_jev_is_asked_per_tier(tmp_path):
    item = reader_item("credit_schedule", tiers(("99.95", "10")), [quote_for("credit_schedule")[0]])
    jev = FakeJev(no=("credit of 25%",))
    build = engine(tmp_path, FakeClaude(reader_override={"credit_schedule": {2: item}}), jev).start(SAMPLE)
    term = next(t for t in build["terms"] if t["field"] == "credit_schedule")
    assert term["agreement"] == {"agree": 2, "of": 3} and term["value"] == EXPECTED["halcyon-a"]["terms"]["credit_schedule"]
    assert [r["yes"] for r in term["jev"]["rows"]] == [True, False] and term["jev"]["yes"] is False
    assert term["needs_acknowledgement"] is True and term["value_in_sentence"] is True and term["rule_value"] == term["value"]
    assert term["second_document_value"] == EXPECTED["halcyon-b"]["terms"]["credit_schedule"] and term["second_document_ok"]
    assert len(term["quote"]) == 2 and term["display"] == "below 99.95%: 10%; below 99.5%: 25%"


def test_the_schedule_is_part_of_the_template_hash_and_the_reading(tmp_path):
    builds, build = approved(tmp_path)
    body = builds.builds[build["id"]]["_template_body"]
    assert body["interpreter"] == "uptime.template_rules/3"
    assert next(r for r in body["rules"] if r["field"] == "credit_schedule")["rows"] == GOOD_RULES["credit_schedule"]["rows"]
    changed = json.loads(json.dumps(body))
    next(r for r in changed["rules"] if r["field"] == "credit_schedule")["rows"][0]["pattern"] += " "
    assert rules.sha256(changed) != build["template"]["sha256"]
    reading = builds.read(build["id"], document_id="halcyon-c")
    schedule_ = next(t for t in reading["terms"] if t["field"] == "credit_schedule")
    assert schedule_["value"] == tiers(("99.99", "15"), ("99.9", "35")) and len(schedule_["quote"]) == 2
    assert builds.approved_readings()[0]["values"]["credit_schedule"] == schedule_["value"]


# --- Version 3.1: a choice rests on the contract's own phrase, not on a list of expected words -------

@pytest.mark.parametrize("field, value, phrase, sentence", [
    ("measurement_period", "calendar_month", "monthly billing cycle",
     "AWS will make the service available with a Monthly Uptime Percentage of at least 99.99% during any monthly billing cycle."),
    ("credit_application", "next_invoice", "against future payments",
     "We will apply any Service Credits only against future payments otherwise due from you."),
    ("credit_application", "next_invoice", "against the Customer's next payment",
     "Credits will be applied against the Customer’s next payment for the Covered Services."),
    ("credit_application", "next_invoice", "credited towards future invoices",
     "Service Credits apply only to the affected resources and are credited towards future invoices."),
])
def test_phrases_the_old_word_list_refused_are_in_their_sentences(field, value, phrase, sentence):
    assert rules.value_in_sentence(field, value, sentence, phrase=phrase)
    assert not hasattr(rules, "CHOICE_WORDS")


def test_a_choice_phrase_not_in_its_sentence_is_refused():
    sentence = "We will apply any Service Credits only against future payments otherwise due from you."
    assert not rules.value_in_sentence("credit_application", "next_invoice", sentence, phrase="against the next invoice")
    assert not rules.value_in_sentence("credit_application", "next_invoice", sentence, phrase="")
    assert not rules.value_in_sentence("credit_application", "next_invoice", sentence)
    assert not rules.value_in_sentence("credit_application", "not_an_option", sentence, phrase="against future payments")
    # numeric terms are unchanged: the number must be in the sentence
    assert not rules.value_in_sentence("credit_cap_percent", "30", "Credits may not exceed 25% of fees.")


def test_readers_must_agree_on_the_phrase_and_jev_is_asked_about_it(tmp_path):
    sentence = quote_for("credit_application")
    other = {"credit_application": {2: {"value": "next_invoice", "phrase": "Service Credits", "quote": sentence}}}
    jev = FakeJev()
    build = engine(tmp_path, FakeClaude(reader_override=other), jev).start(SAMPLE)
    term = next(t for t in build["terms"] if t["field"] == "credit_application")
    assert term["agreement"] == {"agree": 2, "of": 3} and term["phrase"] == "against the next invoice"
    assert term["rule_phrase"] == "against the next invoice" and term["value_in_sentence"] is True
    assert [r["phrase"] for r in term["readers"]] == ["against the next invoice", "Service Credits", "against the next invoice"]
    asked = [c[1] for c in jev.calls if c[0] == "yes_no"]
    assert 'Does this sentence, in the words "against the next invoice", say that a service credit reaches the customer ' \
           'against the next invoice?' in asked
    assert 'Does this sentence, in the words "calendar month", make each calendar month the measurement period?' in asked


def test_a_rule_capturing_other_words_than_the_readers_phrase_does_not_reproduce(tmp_path):
    loose = dict(GOOD_RULES, credit_application={"pattern": r"Service Credits will be applied as a credit against (the next invoice)",
                                                 "map": {"the next invoice": "next_invoice"}})
    claude = FakeClaude(builder_rules=loose, repair_rules=loose)
    build = engine(tmp_path, claude).start(SAMPLE)
    term = next(t for t in build["terms"] if t["field"] == "credit_application")
    # "the next invoice" is not the readers' phrase, so it is pruned from the map and the rule reads nothing.
    assert term["rule_value"] is None and term["rule"]["map"] == {}
    assert check(build, "reproduce")["ok"] is False and term["status"] == "REVIEW"
    assert [c[0] for c in claude.calls].count("repair") == 2
    # Mapped right but capturing other words than the readers' phrase also fails reproduce.
    t = {"type": "choice", "value": "next_invoice", "rule_value": "next_invoice", "phrase": "against the next invoice",
         "rule_phrase": "the next invoice"}
    assert tb._reproduces(t) is False and tb._reproduces(dict(t, rule_phrase="Against the  next invoice")) is True


def test_a_reader_choice_without_a_phrase_fails_value_in_sentence(tmp_path):
    bare = {"measurement_period": {i: {"value": "calendar_month", "quote": quote_for("measurement_period")} for i in (1, 2, 3)}}
    build = engine(tmp_path, FakeClaude(reader_override=bare)).start(SAMPLE)
    term = next(t for t in build["terms"] if t["field"] == "measurement_period")
    assert term["phrase"] is None and term["value_in_sentence"] is False and term["jev"] is None
    assert check(build, "value_in_sentence")["ok"] is False
