"""Independent evidence interlocks for a named build. No gate grants money or sends traffic."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .ramp import RampError
from .ramp_webhooks import strict_json
from .source_config import _check_file, _protected_path, _validated_verifier

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "docs/v4/evidence/release_attestation.json"
REQUIRED_GATES = {"security_financial", "unseen_vendor", "unanticipated_dispute", "regression"}
REVIEW = "human_review"
NATIVE = "native_install"
ACTORS = {**dict.fromkeys(REQUIRED_GATES, "INDEPENDENT_QA"), REVIEW: "ACTUAL_HUMAN", NATIVE: "ACTUAL_NATIVE_OPERATOR"}
SOURCE_DIRS = ("uptime", "web", "tests", "scripts", ".github/workflows",
               *(f"fixtures/{name}" for name in ("correspondence", "disputes", "evidence", "model", "onboarding",
                                                "other_obligations", "pricing", "ramp", "twilio")))
SOURCE_FILES = ("pyproject.toml", "uv.lock", "Open Uptime.command", "fixtures/cp1.json", "docs/v4/evidence/ramp-discovery.json")
HEX = re.compile("[0-9a-f]{64}")
ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError, InvalidSignature,
          InvalidOperation, RampError, subprocess.SubprocessError, RecursionError, OverflowError)


def require(condition):
    if not condition:
        raise ValueError("Release evidence did not verify")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(raw):
    return sha256(raw).hexdigest()


def legacy_digest(value):
    # Producer scripts/blind_acceptance.py predates the release signing framing.
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode())


def code_manifest(root=ROOT):
    root = Path(root).resolve()
    files = [root/name for name in SOURCE_FILES if (root/name).is_file()]
    for name in SOURCE_DIRS:
        folder = root/name
        if folder.exists():
            for p in folder.rglob("*"):
                if "__pycache__" in p.parts or p.suffix in {".pyc", ".pyo"}:
                    continue
                require(not p.is_symlink())
                if p.is_file():
                    files.append(p)
    require(all(p.resolve() == p for p in files))
    return {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in sorted(files)}


def source_identity(root=ROOT, commit=None):
    """Allow a later docs-only commit. Input files must equal the named tested commit."""
    root = Path(root).resolve()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL)
    commit = commit or git("rev-parse", "HEAD").decode().strip()
    require(isinstance(commit, str) and re.fullmatch("[0-9a-f]{40}", commit))
    git("merge-base", "--is-ancestor", commit, "HEAD")
    manifests = code_manifest(root)
    tracked = git("ls-tree", "-rz", "--name-only", commit, "--", *SOURCE_DIRS, *SOURCE_FILES)
    require(set(tracked.decode().split("\0")[:-1]) == set(manifests))
    git("diff", "--no-ext-diff", "--quiet", commit, "--", *SOURCE_DIRS, *SOURCE_FILES)
    require(bool(manifests))
    return {"commit": commit, "manifest_sha256": digest(canonical(manifests))}


def _protected(path, cap=262144):
    path = _protected_path(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as handle:
        _check_file(handle.fileno())
        raw = handle.read(cap+1)
    require(0 < len(raw) <= cap)
    return strict_json(raw)


def _policy(path):
    policy = _protected(path)
    require(set(policy) == {"schema", "roles", "blind", "regression", "baseline_sha256", "campaign"} and policy["schema"] == "uptime-release-trust/1")
    require(HEX.fullmatch(policy["campaign"]))
    roles = policy["roles"]
    require(set(roles) in (set(ACTORS), set(ACTORS)-{NATIVE}))
    for role, reg in roles.items():
        require(set(reg) == {"subject", "public_key", "actor_type"} and reg["actor_type"] == ACTORS[role]
                and re.fullmatch(r"[A-Za-z0-9_.@-]{3,128}", reg["subject"]) and HEX.fullmatch(reg["public_key"]))
        _validated_verifier(reg["public_key"])
    require(len({r["subject"] for r in roles.values()}) == len(roles)
            and len({r["public_key"] for r in roles.values()}) == len(roles))
    return policy


def signing_bytes(role, subject, source, binding, campaign, attempt, issued_at, expires_at):
    return b"uptime-release-witness/v2\0" + canonical({
        "purpose": role, "actor_type": ACTORS[role], "subject": subject, "source": source,
        "binding": binding, "campaign": campaign, "attempt": attempt, "issued_at": issued_at, "expires_at": expires_at})


def _verify(role, policy, source, binding, proof, at):
    require(set(proof) == {"issued_at", "expires_at", "signature", "campaign", "attempt"})
    require(proof["campaign"] == policy["campaign"] and type(proof["attempt"]) is int and proof["attempt"] == 1)
    start, end = proof["issued_at"], proof["expires_at"]
    require(type(start) is int and type(end) is int and start <= at < end and end-start <= 86400)
    sig = proof["signature"]
    require(isinstance(sig, str) and re.fullmatch("[a-f0-9]{128}", sig))
    reg = policy["roles"][role]
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(reg["public_key"])).verify(
        bytes.fromhex(sig), signing_bytes(role, reg["subject"], source, binding, policy["campaign"], proof["attempt"], start, end))


def _read_evidence(path, base):
    path = Path(path)
    require(path.resolve() == path and path.is_relative_to(base) and path.is_file() and path.stat().st_size <= 16_000_000)
    with path.open("rb") as f:
        raw = f.read(16_000_001)
    require(len(raw) <= 16_000_000)
    return raw


def _audit(report, source, root, baseline_sha):
    from scripts import v4_audit_gate as audit
    require(report["schema"] == audit.SCHEMA and report["phase"] == "release" and report["release_pass"] is True
            and report["baseline_commit"] == audit.V3 and report["baseline_verified"] is True
            and report["baseline_error_type"] is None and report["source_stable"] is True and report["driver_stable"] is True)
    require(report["source"] == {"commit": source["commit"], "product_source_sha256": audit.product_hash(root),
                                 "changed_tracked_paths": []})
    gate_files = [root/"scripts/v4_audit_gate.py", *sorted((root/"tests").glob("test_v4_audit_*.py"))]
    require(report["gate_code"] == {str(p.relative_to(root)):digest(p.read_bytes()) for p in gate_files}
            and report["synthetic_input_sha256"] == audit.input_identity(root)
            and report["primary_coverage"] == audit.PRIMARY and report["audit_provenance"] == audit.AUDIT_PROVENANCE)
    rows = report["results"]
    require(report["required_ids"] == sorted(audit.required_ids()) and audit.release_passes(rows)
            and report["counts"] == {"PASS": len(rows)} and all(
                r["execution"] == "OBSERVED" and r["assertion_source"] == "independent-audit-and-known-mutation"
                and canonical(r["observed"]) == canonical(r["expected"]) for r in rows))
    evidence = root/"docs/v4/evidence"
    baseline = _read_evidence(evidence/"security-baseline.json", evidence)
    require(digest(baseline) == baseline_sha)
    before = strict_json(baseline)
    require(before["baseline_commit"] == audit.V3 and before["audit_provenance"] == audit.AUDIT_PROVENANCE
            and before["source"]["materialization"] == "git archive of exact immutable V3 commit"
            and before["source_stable"] is True and before["driver_stable"] is True)
    transitions, valid = audit.compare_before(before, rows)
    require(valid and canonical(transitions) == canonical(report["before_after"])
            and any(t["before"] == "FAIL" for t in transitions))


def _amount(value):
    if value is None:
        return None
    require(isinstance(value, str) and re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value))
    return Decimal(value)


def _blind(report, source, root, pin, gate):
    require(report["protocol"] == "blind-acceptance/2" and report["transport"] == "socket" and report["network_proof"] is True
            and report["authority"] == "SCRIPTED_LOCAL_SYNTHETIC" and report["commercial_authority"] is False
            and report["fail_codes"] == [] and report["gate_2_pass"] is True)
    files = {str(p.relative_to(root)):digest(p.read_bytes()) for p in (root/"uptime").rglob("*.py")}
    require(report["product"] == {"commit": source["commit"], "tree_sha256": legacy_digest(files), "files_count": len(files)}
            and report["runner_sha256"] == digest((root/"scripts/blind_acceptance.py").read_bytes()))
    for key in ("fixture_manifest_sha256", "input_plan_sha256", "public_source_sha256"):
        require(HEX.fullmatch(pin[key]) and report[key] == pin[key])
    obs = report["observations"]
    cases = report["comparison"]["cases"]
    require(len(obs) == len(cases) == report["counts"]["cases"] == pin["case_count"] > 0
            and len({row["case_sha256"] for row in obs}) == len(obs)
            and sorted(r["case_sha256"] for r in obs) == sorted(r["case_sha256"] for r in cases)
            and report["observations_sha256"] == legacy_digest(obs))
    for row in obs:
        lifecycle = row["independent_lifecycle"]
        require(row["fail_codes"] == [] and row["candidate_state"] == "ACTIVE"
                and lifecycle["authority"] == "SCRIPTED_LOCAL_SYNTHETIC" and lifecycle["human_authority"] is False)
        controls = lifecycle["controls"]
        require(len({c["scenario_sha256"] for c in controls}) == len(controls)
                and all(c["passed"] is True and HEX.fullmatch(c["scenario_sha256"]) and HEX.fullmatch(c["readback_sha256"])
                        and c["observed"]["available"] is True for c in controls)
                and any(c["observed"]["outcome"] == "ELIGIBLE" and (_amount(c["observed"]["amount"]) or 0)>0 for c in controls)
                and any(c["observed"]["outcome"] == "INELIGIBLE" for c in controls))
    terms = report["comparison"]["terms"]
    require(terms and all(c["feature"] == "contract_terms" for c in terms) and all(r["checks"] for r in cases))
    checks = terms + [c for r in cases for c in r["checks"]]
    require(all(c["status"] == "PASS" and HEX.fullmatch(c["field_sha256"]) for c in checks)
            and report["check_counts"] == {"PASS":len(checks)}
            and {"money", "decision"} <= {c["feature"] for c in checks})
    # Only this coverage commitment leaves the witness. It pins every checked private assertion,
    # including numeric metric commitments produced by the runner's typed comparisons.
    require(comparison_coverage(report["comparison"]) == pin["comparison_sha256"])
    for c in checks:
        if c["feature"] == "money":
            if "expected_money" in c or "observed_money" in c:
                require(_amount(c["expected_money"]) == _amount(c["observed_money"]))
            else:
                require(HEX.fullmatch(c["expected_sha256"]))
    if gate == "unanticipated_dispute":
        require(report["gate_3_pass"] is True)
        expected = pin["disputes"]
        seen = set()
        for row in obs:
            general = row["generality"]
            require(len(general["checks"]) == general["required_count"] == general["delivered_count"])
            for c in general["checks"]:
                ident = c["message_sha256"]
                require(HEX.fullmatch(ident) and c["delivered"] is True and c["fail_codes"] == []
                        and c["observed"]["available"] is True and c["observed"]["stage"] == expected[ident]["stage"]
                        and _amount(c["observed"]["amount"]) == _amount(expected[ident]["amount"]))
                seen.add(ident)
        require(seen and seen == set(expected))


def comparison_coverage(comparison):
    def fields(rows):
        values = [{k:c[k] for k in ("field_sha256", "feature", "expected_money", "expected_sha256") if k in c} for c in rows]
        return sorted(values, key=canonical)
    return digest(canonical({"terms":fields(comparison["terms"]), "cases":sorted(
        [{"case":r["case_sha256"], "checks":fields(r["checks"])} for r in comparison["cases"]], key=canonical)}))


def _regression(report, source, root, pin):
    require(report["schema"] == "uptime-full-regression/1" and report["source"] == source and report["source_stable"] is True
            and report["runner_sha256"] == digest((root/"scripts/release_regression.py").read_bytes()))
    for suite in ("pytest", "node"):
        data = report[suite]
        require(data["exit_code"] == 0 and type(data["collected"]) is int and data["collected"] > 0
                and data["counts"] == {"passed":data["collected"]} and data["collected"] == pin[suite]["count"]
                and HEX.fullmatch(pin[suite]["collection_sha256"]) and data["collection_sha256"] == pin[suite]["collection_sha256"])
    require(report["node"]["files"] == sorted(str(p.relative_to(root)) for p in (root/"web").glob("*.test.cjs")))


def _bundle(root, receipt, policy, at):
    base = root/"docs/v4/evidence"
    record = strict_json(_read_evidence(receipt, base))
    require(set(record) == {"schema", "scope", "source", "gates", REVIEW}
            and record["schema"] == "uptime-v4-release/2" and record["scope"] == "local-simulation")
    source = source_identity(root, record["source"]["commit"])
    require(source == record["source"] and set(record["gates"]) == REQUIRED_GATES)
    hashes = {}
    for name in sorted(REQUIRED_GATES):
        entry = record["gates"][name]
        require(set(entry) == {"path", "sha256", "proof"} and not Path(entry["path"]).is_absolute())
        raw = _read_evidence(root/entry["path"], base)
        hashes[name] = digest(raw)
        require(entry["sha256"] == hashes[name])
        _verify(name, policy, source, hashes[name], entry["proof"], at)
        report = strict_json(raw)
        observed = datetime.fromisoformat(report["at" if name in {"unseen_vendor","unanticipated_dispute"} else "generated_at"])
        require(observed.utcoffset() is not None and at-86400 < observed.timestamp() <= at
                and observed.timestamp() < entry["proof"]["issued_at"]+1)
        if name == "security_financial":
            _audit(report, source, root, policy["baseline_sha256"])
        elif name == "regression":
            _regression(report, source, root, policy["regression"])
        else:
            _blind(report, source, root, policy["blind"], name)
    # A separate release witness confirms reviewing these exact reports, with zero external authority.
    review = {"scope":"local-simulation", "gates":hashes}
    _verify(REVIEW, policy, source, review, record[REVIEW], at)
    require(all(record[REVIEW]["issued_at"] >= entry["proof"]["issued_at"] for entry in record["gates"].values()))
    return source, digest(canonical(record))


def release_status(root=ROOT, receipt=None, *, trust_path=None):
    root = Path(root).resolve()
    try:
        policy = _policy(trust_path or Path.home()/".config/uptime/release-trust.json")
        _bundle(root, receipt or root/"docs/v4/evidence/release_attestation.json", policy, time.time())
        return {"ready":True, "scope":"local-simulation", "gates":sorted(REQUIRED_GATES),
                "attempt_counts":dict.fromkeys(sorted(REQUIRED_GATES),1),
                "external_authority":False, "note":"Verified local replay release with a separate human release witness."}
    except ERRORS:
        return {"ready":False, "scope":"read-only", "gates":[], "external_authority":False,
                "note":"Local approvals require current independently signed gate reports and a release witness."}


def local_release_ready():
    return release_status()["ready"]


def native_install_ready(installation, *, root=ROOT, trust_path=None, grant_path=None):
    """A release alone cannot arm native routes. Independent grant is re-read on every operation."""
    try:
        root = Path(root).resolve()
        folder = Path.home()/".config/uptime"
        at = time.time()
        policy = _policy(trust_path or folder/"release-trust.json")
        source, release = _bundle(root, root/"docs/v4/evidence/release_attestation.json", policy, at)
        require(set(installation) == {"workspace_id", "tenant", "business_id", "config_sha256"})
        binding = {**installation, "release_sha256":release, "environment":"sandbox", "action":"bill.comment.create"}
        grant = _protected(grant_path or folder/"native-install-release.json")
        require(set(grant) == {"schema", "source", "binding", "proof"} and grant["schema"] == "uptime-native-release/1"
                and grant["source"] == source and grant["binding"] == binding)
        _verify(NATIVE, policy, source, binding, grant["proof"], at)
        return True
    except ERRORS:
        return False
