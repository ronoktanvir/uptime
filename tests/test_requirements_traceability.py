"""The V3 completion checklist keeps every original requirement and cites only real evidence.

This checks the integrity of the record, not the truth of a disposition: a person
still reviews whether MET_LOCAL or PARTIAL is right. Removing or renaming an ID
below is a visible test change that must be explained in the test-change ledger.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/v4/integration90/requirements.json"

PINNED = (
    "O1 O2 O3 O4 O5 O6 "
    "VAL-1 VAL-2 VAL-3 VAL-4 VAL-5 VAL-6 VAL-7 VAL-8 VAL-9 VAL-10 "
    "CP0 CP1 CP2 CP3A CP3B CP4 CP5 CP6 "
    "INV-1 INV-2 INV-3 INV-4 INV-5 INV-6 INV-7 INV-8 "
    "LC-1 LC-2 LC-3 LC-4 "
    "ONB-1 ONB-2 ONB-3 ONB-4 ONB-5 ONB-6 ONB-7 ONB-8 ONB-9 "
    "IF-1 IF-2 IF-3 IF-4 IF-5 IF-6 IF-7 "
    "FIN-1 FIN-2 FIN-3 FIN-4 FIN-5 FIN-6 FIN-7 FIN-8 FIN-9 FIN-10 "
    + " ".join(f"GF-{n}" for n in range(1, 21)) + " "
    "RG-1 RG-2 RG-3 RG-4 RG-5 RG-6 RG-7 "
    "RAMP-1 RAMP-2 RAMP-3 RAMP-4 RAMP-5 RAMP-6 RAMP-7 RAMP-AUTH "
    "AG-1 AG-2 AG-3 AG-4 AG-5 AG-6 AG-7 AG-8 "
    + " ".join(f"API-{n}" for n in range(1, 15)) + " "
    "STACK-1 STACK-2 STACK-3 STACK-4 STACK-5 DB-1 SEC-1 CONT-1 OAUTH-1 "
    "UI-1 UI-2 UI-3 UI-4 UI-5 UI-6 UI-7 UI-8 UI-9 "
    "DEMO-TWILIO DEMO-PRICE DEMO-ATLASSIAN DEMO-SLACK SIM-1 "
    "CRED-1 CRED-2 CRED-3 CRED-4 "
    "OBL-1 OBL-2 OBL-3 OBL-4 OBL-5 OBL-6 OBL-7 "
    "ORCH-1 ORCH-2 ORCH-3 ORCH-4 ORCH-5 ART-1 "
    + " ".join(f"CRIT-{n}" for n in range(1, 15)) + " "
    + " ".join(f"SPEC11-{n}" for n in range(1, 17))
).split()

DISPOSITIONS = {"MET", "MET_LOCAL", "PARTIAL", "NOT_MET", "SUPERSEDED"}
CLASSES = {"bug", "missing_functionality", "unverified_behavior", "external_dependency"}
DECISION = re.compile(r"^D(0[1-9]|1[0-4])$")


@pytest.fixture(scope="module")
def data():
    return json.loads(SOURCE.read_text())


def test_every_original_requirement_keeps_exactly_one_disposition(data):
    ids = [r["id"] for r in data["requirements"]]
    assert len(ids) == len(set(ids))
    assert sorted(ids) == sorted(PINNED)


def test_record_fields_use_closed_vocabularies(data):
    owners = set(data["owners"])
    assert set(data["gap_classes"]) == CLASSES
    assert set(data["dispositions"]) == DISPOSITIONS
    for r in data["requirements"]:
        assert r["disposition"] in DISPOSITIONS, r["id"]
        assert r["owner"] in owners, r["id"]
        assert r["gap_class"] in CLASSES | {None}, r["id"]
        assert all(DECISION.match(d) for d in r["decisions"]), r["id"]
        assert r["requirement"].strip() and r["source"].startswith("docs/uptime-v3/"), r["id"]


def test_incomplete_items_name_their_gap_class_and_owner(data):
    for r in data["requirements"]:
        if r["disposition"] in ("PARTIAL", "NOT_MET"):
            assert r["gap"] and r["gap_class"], r["id"]
        if r["disposition"] == "SUPERSEDED":
            assert r["gap"] and r["evidence"], r["id"]  # the gap text names the superseding direction
        if r["gap_class"]:
            assert r["gap"], r["id"]


def test_completion_claims_cite_evidence(data):
    for r in data["requirements"]:
        if r["disposition"] in ("MET", "MET_LOCAL"):
            assert r["evidence"], r["id"]


def test_every_cited_file_and_test_function_exists(data):
    missing = []
    for r in data["requirements"]:
        for item in [r["source"], *r["implementation"], *r["evidence"]]:
            path, _, name = item.partition("::")
            target = ROOT / path.partition("#")[0]
            if not target.is_file():
                missing.append((r["id"], item))
            elif name and not re.search(rf"^def {re.escape(name)}\(", target.read_text(), re.M):
                missing.append((r["id"], item))
    assert not missing


def test_rendered_checklist_matches_source():
    result = subprocess.run([sys.executable, "scripts/render_requirements.py", "--check"], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
