"""Regression suite for the public phase85 operational evaluation harness.

Contract: docs/v4/evaluation85/HARNESS-INTERFACE.md
Fixture:  docs/v4/evaluation85/test_control.json -- an openly authored harness
          control. It is not the independent84 corpus, not gold and not a model
          result, so nothing here asserts corpus, extraction or monetary values.

Only ``uptime.vendor_model_jobs.build_vendor_provider`` is replaced, by a
recording provider double whose instances share one call log. Prepare, the
explicit protected approval, the proposal queue, the signed loopback app and
shadow preview all run through their real code paths inside ``run_attempt``.
The protected config names ``/usr/bin/true`` so even an unpatched provider
could not perform inference.

Assumptions the interface text does not pin down (each lives in one place):
* protected config file schema            -> ``_write_protected_config``
* module that defines ``VENDOR_SYSTEM``   -> ``_vendor_system``
* ``approve(expected_digest=...)`` is prepare's ``request_sha256`` -> ``_World.approve``
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

import pytest

import scripts.evaluate_onboarding_85 as harness
from scripts import public_proposals
from uptime import vendor_model, vendor_model_jobs

CONTROL_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "v4" / "evaluation85" / "test_control.json"
)
CONTROL = json.loads(CONTROL_PATH.read_text(encoding="utf-8"))

CASE_ID = "local-case-85"
TENANT = "local-tenant-85"
SUBJECT = "local-subject-85"
APPROVER = "harness85-test-operator"
FAMILY = "monthly_tier"
PROFILE = "monthly-propositions"
DECLARED_PROFILES = {
    "monthly_tier": "monthly-propositions",
    "completed_step": "monthly-propositions",
    "unsupported_variable_fee": "monthly-propositions",
    "ambiguous_deadline": "monthly-propositions",
    "resource_month": "resource-month",
    "aggregate_fixed_month": "resource-month",
}
ATTEMPT_FILES = frozenset(
    {"document.json", "customer.json", "request-export.json", "request.json", "frozen.json"}
)
REPORT_KEYS = frozenset(
    {"case_id", "profile", "failure_stage", "extraction", "shadow", "deterministic", "authority"}
)

DOUBLE_PROFILE = {"provider": "harness85-recording-double", "revision": "1"}
DOUBLE_SESSION = "harness85-double-session"
RECEIPT_MARKER = "harness85-double-transport-receipt"
FABRICATED_MODEL = "harness85-fabricated-model-identity"
VALID_TEXT = json.dumps(CONTROL["proposal"])

EXPECTED_MARKER = "HARNESS85_SIBLING_EXPECTED_SENTINEL"
EXPECTED_SENTINEL = (json.dumps({"sentinel": EXPECTED_MARKER}) + "\n").encode("utf-8")
AUTHORED_PLACEHOLDER = {"authored_placeholder": "harness mechanics only"}

_HEX64 = re.compile(r"[0-9a-f]{64}")
# A refusal must be a deliberate error, not a crash from a missing/miswired implementation.
_PROGRAMMING_ERRORS = (
    TypeError,
    AttributeError,
    NameError,
    ImportError,
    NotImplementedError,
    AssertionError,
)


# --------------------------------------------------------------------------- helpers


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def _customer_local_markers() -> list[str]:
    """Customer-only strings: present in customer.json, absent from the vendor text."""
    text = CONTROL["document"]["text"]
    markers = sorted(
        {s for s in _strings(CONTROL["customer"]) if len(s) >= 6 and s not in text}
    )
    assert markers, "control must carry customer-only values for the separation check"
    return markers


def _private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def _write_private(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    os.chmod(path, 0o600)


def _write_protected_config(protected: Path, approvals_path: Path) -> Path:
    # SCHEMA ASSUMPTION: HARNESS-INTERFACE.md requires a protected config naming the
    # provider executable (/usr/bin/true is allowed because the factory is patched)
    # and the protected approvals store, but does not spell out the file schema
    # consumed by uptime.source_config.load_private / PublicProposalConfig.
    # Reconcile the keys here, and only here, with the real loader.
    config = protected / "public-proposal-config.json"
    _write_private(
        config,
        _json_bytes({"executable": "/usr/bin/true", "approvals_path": str(approvals_path)}),
    )
    return config


def _vendor_system():
    # ASSUMPTION: the interface names VENDOR_SYSTEM beside uptime.vendor_model.MODEL
    # without giving its module; this is the only place it is resolved.
    return vendor_model.VENDOR_SYSTEM


def _tree(root: Path) -> set[Path]:
    return set(root.rglob("*"))


def _append_newline(path: Path) -> None:
    """Change raw bytes (and so the SHA) while keeping the JSON parseable."""
    mode = stat.S_IMODE(path.stat().st_mode)
    os.chmod(path, mode | stat.S_IWUSR)
    with open(path, "ab") as handle:
        handle.write(b"\n")
    os.chmod(path, mode)


def _assert_refuses(call) -> None:
    with pytest.raises(Exception) as caught:
        call()
    assert not isinstance(caught.value, _PROGRAMMING_ERRORS), (
        f"refusal surfaced as a programming error: {caught.value!r}"
    )


def _assert_source_only(request: bytes, world: "_World") -> None:
    """Only vendor document text (plus existing instructions) may be transmitted."""
    assert any(CONTROL["document"]["text"] in s for s in _strings(json.loads(request))), (
        "document text must be transmitted verbatim"
    )
    local = _customer_local_markers() + [
        CASE_ID,
        TENANT,
        SUBJECT,
        EXPECTED_MARKER,
        str(world.root),
        os.path.realpath(world.root),
    ]
    assert [m for m in local if m.encode("utf-8") in request] == []


def _assert_public_report(report: dict) -> None:
    assert REPORT_KEYS <= set(report)
    assert report["case_id"] == CASE_ID
    assert report["profile"] == PROFILE
    assert report["authority"]["promotion_performed"] is False
    assert not {"stdout", "stderr"} & set(_keys(report))
    # The transport receipt is retained separately, never in the public report.
    assert RECEIPT_MARKER not in json.dumps(report)


def _assert_not_attempted(report: dict, stage: str) -> None:
    assert report["failure_stage"] == stage
    assert report["extraction"]["status"] == "NOT_ATTEMPTED"
    assert report["shadow"]["status"] == "NOT_ATTEMPTED"
    assert report["deterministic"] == []


def _assert_retained(world: "_World", report: dict) -> None:
    on_disk = json.loads((world.attempt_dir / "report.json").read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(report))
    lines = [
        line
        for line in (world.attempt_dir / "progress.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines
    for line in lines:
        json.loads(line)


# --------------------------------------------------------------------------- audit spy
# A process-wide audit hook records every path passed to open()/io.open/os.open
# (including from server threads) while a test has recording enabled. It only
# records names; the sentinel's contents are never loaded by the test.

_AUDIT: dict = {"log": None, "installed": False}


def _audit_hook(event, args):
    log = _AUDIT["log"]
    if log is None or event != "open" or not args:
        return
    target = args[0]
    if isinstance(target, (str, bytes, os.PathLike)):
        try:
            log.append(os.fsdecode(target))
        except Exception:
            pass


@contextlib.contextmanager
def _audit_opens():
    if not _AUDIT["installed"]:
        sys.addaudithook(_audit_hook)
        _AUDIT["installed"] = True
    log: list[str] = []
    _AUDIT["log"] = log
    try:
        yield log
    finally:
        _AUDIT["log"] = None


@contextlib.contextmanager
def _audit_paused():
    saved = _AUDIT["log"]
    _AUDIT["log"] = None
    try:
        yield
    finally:
        _AUDIT["log"] = saved


# --------------------------------------------------------------------------- provider double


class _ProviderLog:
    """State shared by every double built by the patched factory."""

    def __init__(self) -> None:
        self.calls: list = []
        self.output = "valid"
        self.profile = dict(DOUBLE_PROFILE)


def _model_output(mode: str) -> tuple[str, str]:
    if mode == "valid":
        return vendor_model.MODEL, VALID_TEXT
    if mode == "malformed":
        return vendor_model.MODEL, VALID_TEXT[: len(VALID_TEXT) // 2]
    if mode == "fenced":
        return vendor_model.MODEL, f"```json\n{VALID_TEXT}\n```"
    if mode == "fabricated_model":
        return FABRICATED_MODEL, VALID_TEXT
    raise AssertionError(f"unknown double output mode {mode!r}")


class _ProviderDouble:
    def __init__(self, log: _ProviderLog) -> None:
        self._log = log
        self.model = vendor_model.MODEL
        self.system = _vendor_system()
        self.profile = dict(log.profile)
        self.last_receipt = None

    def __call__(self, request):
        self._log.calls.append(request)
        model, text = _model_output(self._log.output)
        self.last_receipt = {"transport": RECEIPT_MARKER}
        return {"model": model, "session": DOUBLE_SESSION, "text": text}


# --------------------------------------------------------------------------- world


class _World:
    def __init__(self, root: Path, log: _ProviderLog) -> None:
        self.root = root
        self.log = log
        self.opened: list[str] = []
        self.sources = root / "frozen-sources"
        self.base_source = self.write_source("base")
        self.base_dir = self.base_source["document_path"].parent
        protected = _private_dir(root / "protected")
        self.approvals_path = protected / "approvals.json"
        self.config_path = _write_protected_config(protected, self.approvals_path)
        self.attempt_dir = _private_dir(root / "attempts") / "attempt-85"

    def write_source(
        self,
        label: str,
        *,
        document=None,
        customer=None,
        document_name: str = "document.json",
        customer_name: str = "customer.json",
    ) -> dict:
        folder = self.sources / label
        folder.mkdir(parents=True)
        document_bytes = _json_bytes(CONTROL["document"] if document is None else document)
        customer_bytes = _json_bytes(CONTROL["customer"] if customer is None else customer)
        (folder / document_name).write_bytes(document_bytes)
        (folder / customer_name).write_bytes(customer_bytes)
        with _audit_paused():  # the test, not the harness, authors the sibling sentinel
            (folder / "expected.json").write_bytes(EXPECTED_SENTINEL)
        return {
            "document_path": folder / document_name,
            "document_sha256": _sha256(document_bytes),
            "customer_path": folder / customer_name,
            "customer_sha256": _sha256(customer_bytes),
        }

    def prepare(self, **overrides) -> dict:
        kwargs = {
            "case_id": CASE_ID,
            "family": FAMILY,
            **self.base_source,
            "config_path": self.config_path,
            "attempt_dir": self.attempt_dir,
            "tenant": TENANT,
            "subject": SUBJECT,
        }
        kwargs.update(overrides)
        return harness.prepare_case(**kwargs)

    def approve(self, prepared: dict) -> None:
        # Explicit authored test inference permission through the existing helper.
        # ASSUMPTION: expected_digest is the request digest prepare returned.
        public_proposals.approve(
            self.attempt_dir / "request-export.json",
            self.approvals_path,
            approved_by=APPROVER,
            expected_digest=prepared["request_sha256"],
            public_confirmed=True,
        )

    def run(self) -> dict:
        return harness.run_attempt(attempt_dir=self.attempt_dir, config_path=self.config_path)

    def assert_gold_never_opened(self) -> None:
        touched = [p for p in list(self.opened) if os.path.basename(p).lower() == "expected.json"]
        assert touched == [], f"sibling expected.json was opened: {touched}"


def _only(source: dict, side: str) -> dict:
    return {f"{side}_path": source[f"{side}_path"], f"{side}_sha256": source[f"{side}_sha256"]}


@pytest.fixture
def provider_log(monkeypatch) -> _ProviderLog:
    log = _ProviderLog()

    def build_vendor_provider(*args, **kwargs):
        return _ProviderDouble(log)

    monkeypatch.setattr(vendor_model_jobs, "build_vendor_provider", build_vendor_provider)
    return log


@pytest.fixture
def world(tmp_path, provider_log):
    built = _World(tmp_path, provider_log)
    with _audit_opens() as opened:
        built.opened = opened
        yield built


# --------------------------------------------------------------------------- prepare


def test_prepare_freezes_attempt_without_inference_and_transmits_source_only(world):
    before = _tree(world.root)

    prepared = world.prepare()

    assert world.log.calls == []
    assert {"profile", "request_sha256", "context_sha256", "case_id"} <= set(prepared)
    assert prepared["case_id"] == CASE_ID
    assert prepared["profile"] == PROFILE
    assert _HEX64.fullmatch(prepared["request_sha256"])
    assert _HEX64.fullmatch(prepared["context_sha256"])

    attempt = world.attempt_dir
    assert stat.S_IMODE(attempt.stat().st_mode) == 0o700
    names = {p.name for p in attempt.iterdir()}
    assert ATTEMPT_FILES <= names
    assert names - ATTEMPT_FILES <= {"progress.jsonl"}  # no run-started/report/queue/DB/key
    for name in ATTEMPT_FILES:
        assert stat.S_IMODE((attempt / name).stat().st_mode) == 0o600, name
    created = _tree(world.root) - before
    assert all(p == attempt or attempt in p.parents for p in created), sorted(created)
    assert not world.approvals_path.exists()

    assert (attempt / "document.json").read_bytes() == world.base_source[
        "document_path"
    ].read_bytes()
    assert (attempt / "customer.json").read_bytes() == world.base_source[
        "customer_path"
    ].read_bytes()

    request = (attempt / "request.json").read_bytes()
    assert _sha256(request) == prepared["request_sha256"]
    _assert_source_only(request, world)

    export = (attempt / "request-export.json").read_bytes()
    assert [
        m for m in _customer_local_markers() + [EXPECTED_MARKER] if m.encode("utf-8") in export
    ] == []

    frozen = (attempt / "frozen.json").read_text(encoding="utf-8")
    json.loads(frozen)
    for pin in (
        world.base_source["document_sha256"],
        world.base_source["customer_sha256"],
        prepared["request_sha256"],
    ):
        assert pin in frozen

    for path in attempt.iterdir():
        assert EXPECTED_MARKER.encode("utf-8") not in path.read_bytes(), path.name
    world.assert_gold_never_opened()


@pytest.mark.parametrize(("family", "profile"), sorted(DECLARED_PROFILES.items()))
def test_declared_family_labels_map_to_profiles(world, family, profile):
    prepared = world.prepare(family=family)

    assert prepared["profile"] == profile
    assert world.log.calls == []
    world.assert_gold_never_opened()


def _refuse_unknown_family(w):
    return {"family": "unknown_family_label"}


def _refuse_profile_name_as_family(w):
    return {"family": PROFILE}


def _refuse_document_sha(w):
    return {"document_sha256": _sha256(b"not the independently frozen document")}


def _refuse_customer_sha(w):
    return {"customer_sha256": w.base_source["document_sha256"]}


def _refuse_document_name(w):
    return _only(w.write_source("renamed-document", document_name="source-document.json"), "document")


def _refuse_customer_name(w):
    return _only(w.write_source("renamed-customer", customer_name="customer-local.json"), "customer")


def _refuse_document_is_expected(w):
    return {
        "document_path": w.base_dir / "expected.json",
        "document_sha256": _sha256(EXPECTED_SENTINEL),
    }


def _refuse_customer_is_expected(w):
    return {
        "customer_path": w.base_dir / "expected.json",
        "customer_sha256": _sha256(EXPECTED_SENTINEL),
    }


def _refuse_document_expected_field(w):
    document = {**CONTROL["document"], "expected": AUTHORED_PLACEHOLDER}
    return _only(w.write_source("document-expected", document=document), "document")


def _refuse_customer_expected_field(w):
    customer = {**CONTROL["customer"], "expected": AUTHORED_PLACEHOLDER}
    return _only(w.write_source("customer-expected", customer=customer), "customer")


def _refuse_scenario_expected_field(w):
    customer = json.loads(json.dumps(CONTROL["customer"]))
    customer["scenarios"][0]["expected"] = AUTHORED_PLACEHOLDER
    return _only(w.write_source("scenario-expected", customer=customer), "customer")


def _refuse_existing_attempt_dir(w):
    _private_dir(w.attempt_dir)
    return {}


REFUSALS = {
    "unknown_family_label": _refuse_unknown_family,
    "profile_name_is_not_a_family": _refuse_profile_name_as_family,
    "document_sha_mismatch": _refuse_document_sha,
    "customer_sha_mismatch": _refuse_customer_sha,
    "document_wrong_name": _refuse_document_name,
    "customer_wrong_name": _refuse_customer_name,
    "document_path_is_expected_json": _refuse_document_is_expected,
    "customer_path_is_expected_json": _refuse_customer_is_expected,
    "document_extra_expected_field": _refuse_document_expected_field,
    "customer_extra_expected_field": _refuse_customer_expected_field,
    "scenario_extra_expected_field": _refuse_scenario_expected_field,
    "attempt_dir_not_new": _refuse_existing_attempt_dir,
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_prepare_refuses_invalid_inputs_before_reading_gold(world, case):
    overrides = REFUSALS[case](world)

    _assert_refuses(lambda: world.prepare(**overrides))

    assert world.log.calls == []
    assert not (world.attempt_dir / "request.json").exists()
    assert not (world.attempt_dir / "frozen.json").exists()
    assert not world.approvals_path.exists()
    world.assert_gold_never_opened()

    # Positive control: the unmodified inputs prepare cleanly, so the refusal
    # above is attributable to the single changed input, not a broken setup.
    control = world.prepare(attempt_dir=world.attempt_dir.parent / "control-attempt")
    assert control["profile"] == PROFILE
    assert world.log.calls == []
    world.assert_gold_never_opened()


# --------------------------------------------------------------------------- run


def test_missing_approval_is_retained_permission_failure_with_zero_calls(world):
    prepared = world.prepare()

    report = world.run()

    assert world.log.calls == []
    _assert_public_report(report)
    _assert_not_attempted(report, "permission")
    _assert_retained(world, report)

    # Approving afterwards cannot revive an attempt that already started.
    world.approve(prepared)
    with pytest.raises(FileExistsError):
        world.run()
    assert world.log.calls == []
    world.assert_gold_never_opened()


def _drift_frozen_document(w):
    _append_newline(w.attempt_dir / "document.json")


def _drift_frozen_customer(w):
    _append_newline(w.attempt_dir / "customer.json")


def _drift_frozen_request(w):
    _append_newline(w.attempt_dir / "request.json")


def _drift_source_document(w):
    _append_newline(w.base_source["document_path"])


def _drift_provider_profile(w):
    w.log.profile = {**DOUBLE_PROFILE, "revision": "drifted"}


DRIFTS = {
    "frozen_document": _drift_frozen_document,
    "frozen_customer": _drift_frozen_customer,
    "frozen_request": _drift_frozen_request,
    "source_document_pin": _drift_source_document,
    "provider_profile_pin": _drift_provider_profile,
}


@pytest.mark.parametrize("drift", sorted(DRIFTS))
def test_pin_drift_is_retained_failure_with_zero_calls(world, drift):
    prepared = world.prepare()
    world.approve(prepared)
    DRIFTS[drift](world)

    report = world.run()

    assert world.log.calls == []
    _assert_public_report(report)
    _assert_not_attempted(report, "frozen_inputs")
    _assert_retained(world, report)
    world.assert_gold_never_opened()


def test_approved_attempt_makes_one_call_and_previews_shadow_without_promotion(world):
    prepared = world.prepare()
    world.approve(prepared)
    request = (world.attempt_dir / "request.json").read_bytes()

    report = world.run()

    # Exactly one provider call carrying exactly the frozen, approved bytes.
    assert world.log.calls == [request]
    assert isinstance(world.log.calls[0], bytes)
    _assert_source_only(world.log.calls[0], world)

    _assert_public_report(report)
    assert report["failure_stage"] is None
    assert report["extraction"]["status"] == "SUCCEEDED"
    assert report["extraction"].get("job_id")
    assert report["shadow"]["status"] == "SHADOW"
    assert report["authority"]["promotion_performed"] is False

    # One signed shadow-preview per local scenario; values are not gold-checked.
    scenarios = CONTROL["customer"]["scenarios"]
    assert [entry["name"] for entry in report["deterministic"]] == [s["name"] for s in scenarios]
    for entry in report["deterministic"]:
        assert entry["http_status"] == 200
        assert entry["result"]

    _assert_retained(world, report)
    world.assert_gold_never_opened()


def test_started_attempt_cannot_run_twice(world):
    prepared = world.prepare()
    world.approve(prepared)
    first = world.run()
    assert first["failure_stage"] is None
    assert len(world.log.calls) == 1
    retained = {
        name: (world.attempt_dir / name).read_bytes()
        for name in ("run-started.json", "report.json", "progress.jsonl")
    }

    with pytest.raises(FileExistsError):
        world.run()

    assert len(world.log.calls) == 1
    assert {
        name: (world.attempt_dir / name).read_bytes() for name in retained
    } == retained
    world.assert_gold_never_opened()


@pytest.mark.parametrize("output", ["malformed", "fenced", "fabricated_model"])
def test_unusable_model_output_refuses_without_candidate(world, output):
    world.log.output = output
    prepared = world.prepare()
    world.approve(prepared)

    report = world.run()

    assert len(world.log.calls) == 1  # never retried
    _assert_public_report(report)
    assert report["failure_stage"] == "extraction"
    assert report["extraction"]["status"] == "REFUSED"
    assert report["shadow"]["status"] == "NOT_ATTEMPTED"
    assert report["deterministic"] == []
    _assert_retained(world, report)
    world.assert_gold_never_opened()


def test_sibling_expected_json_is_never_opened_by_prepare_or_run(world):
    prepared = world.prepare()
    world.approve(prepared)
    report = world.run()
    assert report["failure_stage"] is None  # the guard covered the full run path

    opened = {os.path.realpath(p) for p in list(world.opened)}
    # Liveness: the spy must have seen prepare read the frozen source, otherwise
    # the absence check below would pass vacuously.
    assert os.path.realpath(world.base_source["document_path"]) in opened
    world.assert_gold_never_opened()
