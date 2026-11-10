"""Demo line: the template builder (docs/demo/TEMPLATE-BUILDER.md) with a fake Claude and a fake Jev.

No network, no Claude Code CLI: `claude(system, prompt)` and Jev are stand-ins defined here. The interpreter, the
checks, approval by SHA-256 and the post-approval read are the real code.
"""
from decimal import Decimal
import json
import os
from pathlib import Path
import re

from fastapi.testclient import TestClient
import pytest

from scripts import setup_northwind as setup
from uptime import template_rules as rules
from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient
from uptime.template_builder import FIXTURES, TemplateBuilds

EXPECTED = json.loads((FIXTURES / "expected.json").read_text())
SAMPLE = "halcyon-availability-addendum"
TEXT_A = rules.normalize((FIXTURES / "halcyon-a.txt").read_text())

GOOD_RULES = {
    "availability_target_percent": {"pattern": r"Platform Availability of at least (\d+(?:\.\d+)?)%"},
    "measurement_period": {"pattern": r'"Measurement Period" means each (calendar \w+)',
                           "map": {"calendar month": "calendar_month"}},
    "tier_1_credit_percent": {"pattern": r"\(a\) where Platform Availability is less than [\d.]+% but equal to or "
                                         r"greater than [\d.]+%, a Service Credit of (\d+(?:\.\d+)?)%"},
    "tier_2_threshold_percent": {"pattern": r"\(b\) where Platform Availability is less than (\d+(?:\.\d+)?)%"},
    "tier_2_credit_percent": {"pattern": r"\(b\) where Platform Availability is less than [\d.]+%, a Service Credit "
                                         r"of (\d+(?:\.\d+)?)%"},
    "credit_cap_percent": {"pattern": r"will not exceed [a-z-]+ percent \((\d+(?:\.\d+)?)%\)"},
    "claim_window_days": {"pattern": r"submit a written claim to \S+ within [a-z-]+ \((\d+)\) days"},
    "maintenance_notice_hours": {"pattern": r"scheduled maintenance on the Covered Services, provided that it gives "
                                            r"Customer at least [a-z-]+ \((\d+)\) hours"},
    "credit_application": {"pattern": r"Service Credits will be applied as a credit (against the next invoice)",
                           "map": {"against the next invoice": "next_invoice"}},
}


def quote_for(field):
    """The sentence of document A that a careful reader would quote, found with the good rule."""
    found = rules.run_rule({"field": field, **GOOD_RULES[field]}, TEXT_A)
    assert found["value"] is not None, field
    return found["quote"]


class FakeClaude:
    """Answers reader, builder and repair prompts; records every prompt."""

    def __init__(self, reader_override=None, builder_rules=None, repair_rules=None, fail_reader=()):
        self.calls = []
        self.reader_override = reader_override or {}
        self.builder_rules = builder_rules or GOOD_RULES
        self.repair_rules = repair_rules or GOOD_RULES
        self.fail_reader = set(fail_reader)
        self.readers = 0

    def __call__(self, system, prompt):
        self.calls.append(prompt)
        if prompt.startswith("Read the contract below"):
            self.readers += 1
            index = self.readers
            if index in self.fail_reader:
                return "Sorry, I cannot help with that."
            terms = {f: {"value": v, "quote": quote_for(f)} for f, v in EXPECTED["halcyon-a"]["terms"].items()}
            for field, by_reader in self.reader_override.items():
                if index in by_reader:
                    terms[field] = by_reader[index]
            return "```json\n" + json.dumps({"terms": terms}) + "\n```"
        fields = re.search(r"with exactly these fields: ([a-z_, 0-9]+)\.", prompt).group(1).split(", ")
        source = self.repair_rules if prompt.startswith("Some extraction rules") else self.builder_rules
        return json.dumps({"rules": {f: source[f] for f in fields}})


class FakeJev:
    def __init__(self, unreachable=False, probability="0.97"):
        self.unreachable, self.probability, self.calls = unreachable, Decimal(probability), []

    def choice(self, question, options, context):
        self.calls.append("choice")
        if self.unreachable:
            raise ConnectionError("no route")
        return {"choice": "unrecognised", "probability": Decimal("0.96"), "model": "jev-test", "milliseconds": 1}

    def yes_no(self, question, context):
        self.calls.append(question)
        if self.unreachable:
            raise ConnectionError("no route")
        return {"yes": True, "probability": self.probability, "model": "jev-test", "milliseconds": 1}


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


def check(build, ident):
    return next(c for c in build["checks"] if c["id"] == ident)


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
    assert all(c["ok"] for c in build["checks"]), build["checks"]
    assert check(build, "quotes")["total"] == 27 and check(build, "jev")["ran"] is True
    assert {t["field"]: t["value"] for t in build["terms"]} == EXPECTED["halcyon-a"]["terms"]
    assert all(t["status"] == "PASS" for t in build["terms"])
    assert build["terms"][0]["display"] == "99.95%" and build["terms"][0]["jev"]["probability"] == "0.97"
    assert len(claude.calls) == 4  # three readers and one builder, no repair
    listing = client.get("/api/template-builds", headers=actor.headers).json()
    assert listing["enabled"] and listing["samples"][0]["document"]["text_url"].endswith("halcyon-a.txt")
    assert "_path" not in json.dumps(listing) and "_expected" not in json.dumps(listing)
    text = client.get(listing["samples"][0]["document"]["text_url"], headers=actor.headers)
    assert text.status_code == 200 and "Platform Availability Addendum".upper() in text.text
    sha = build["template"]["sha256"]
    approved = actor.post(f"/api/template-builds/{build['id']}/approve", {"template_sha256": sha})
    assert approved.status_code == 200, approved.text
    approved = approved.json()["build"]
    assert approved["state"] == "APPROVED" and approved["template"]["approved_by"] == SCRIPT
    calls_before = len(claude.calls)
    reading = actor.post(f"/api/template-builds/{build['id']}/read", {"document_id": "halcyon-c"}).json()["reading"]
    assert reading["model_calls"] == 0 and reading["read_by"] == "TEMPLATE" and len(claude.calls) == calls_before
    assert {t["field"]: t["value"] for t in reading["terms"]} == EXPECTED["halcyon-c"]["terms"]
    assert reading["found"] == reading["total"] == 9 and reading["template"]["sha256"] == sha
    assert all(t["quote"] and t["quote"] in rules.normalize((FIXTURES / "halcyon-c.txt").read_text()) for t in reading["terms"])
    stored = tmp_path / "template-builds" / (build["id"] + ".json")
    assert stat_mode(stored) == 0o600


def test_only_the_listed_sample_texts_are_served(served):
    client, actor = served[1], served[2]
    assert client.get("/fixtures/template_builder_demo/halcyon-a.txt", headers=actor.headers).status_code == 200
    for name in ("expected.json", "samples.json", "README.md", "halcyon-z.txt"):
        assert client.get("/fixtures/template_builder_demo/" + name, headers=actor.headers).status_code == 404, name


def stat_mode(path):
    return os.stat(path).st_mode & 0o777


def test_reader_disagreement_marks_the_term_for_review(served, tmp_path):
    override = {"credit_cap_percent": {3: {"value": "25", "quote": quote_for("credit_cap_percent")}}}
    build = run(served, tmp_path, FakeClaude(reader_override=override), FakeJev())
    term = next(t for t in build["terms"] if t["field"] == "credit_cap_percent")
    assert term["value"] == "30" and term["agreement"] == {"agree": 2, "of": 3} and term["status"] == "REVIEW"
    assert check(build, "agreement")["ok"] is False and check(build, "agreement")["blocking"] is False
    assert build["state"] == "READY_FOR_REVIEW"


def test_a_quote_not_in_the_contract_blocks_approval(served, tmp_path):
    invented = {"claim_window_days": {2: {"value": "30", "quote": "Claims may be filed within thirty days."}}}
    build = run(served, tmp_path, FakeClaude(reader_override=invented), FakeJev())
    quotes = check(build, "quotes")
    assert quotes["ok"] is False and quotes["passed"] == 26 and quotes["total"] == 27
    response = served[2].post(f"/api/template-builds/{build['id']}/approve",
                              {"template_sha256": build["template"]["sha256"]})
    assert response.status_code == 409 and "blocking check" in response.json()["detail"]


def test_a_rule_that_fails_on_the_second_document_is_repaired(served, tmp_path):
    hardwired = dict(GOOD_RULES, claim_window_days={"pattern": r"within (thirty) \(\d+\) days after the end"})
    claude = FakeClaude(builder_rules=hardwired)
    build = run(served, tmp_path, claude, FakeJev())
    repair = [p for p in claude.calls if p.startswith("Some extraction rules")]
    assert len(repair) == 1 and "claim_window_days" in repair[0] and "SECOND CONTRACT" in repair[0]
    assert '"45"' not in repair[0]  # never shown the second document's expected value
    assert build["steps"][4]["detail"]["repair_rounds"] == 1
    assert check(build, "second_document")["ok"] and check(build, "reproduce")["ok"]


def test_jev_unreachable_still_reaches_review(served, tmp_path):
    build = run(served, tmp_path, FakeClaude(), FakeJev(unreachable=True))
    assert build["state"] == "READY_FOR_REVIEW"
    assert build["steps"][0]["state"] == "FAILED" and "Jev could not be reached" in build["steps"][0]["summary"]
    assert all(t["jev"] is None for t in build["terms"])
    jev = check(build, "jev")
    assert jev["ran"] is False and jev["ok"] is False and jev["lowest"] is None


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
    timed = rules.run_rule({"field": "claim_window_days", "pattern": r"(a+)+b"}, "a" * 40)
    assert timed["value"] is None and "longer than" in timed["error"]
    hard = rules.run_rule({"field": "claim_window_days", "pattern": r"within thirty \((30)\) days"}, TEXT_A)
    assert hard["value"] is None and "spells out" in hard["error"]
    assert "compile" in rules.run_rule({"field": "claim_window_days", "pattern": "(unclosed"}, TEXT_A)["error"]
    assert "exactly one" in rules.run_rule({"field": "claim_window_days", "pattern": "within"}, TEXT_A)["error"]
    assert rules.canonical("percent", "99.50%") == "99.5" and rules.canonical("percent", "abc") is None
