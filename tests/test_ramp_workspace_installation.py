from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key
from uptime.ramp import RampError
from uptime.ramp_records import seal_snapshot
from uptime.ramp_workspace import PACKAGED, RampWorkspace
from uptime.server import create_app
from uptime.storage import case_versions
from uptime.workbench import Workbench


def capture(offset=0):
    observed=json.loads(PACKAGED.read_text())
    moment=datetime.now(UTC)+timedelta(seconds=offset-5)
    observed["observed_at"]=moment.isoformat()
    observed["completed_at"]=(moment+timedelta(seconds=1)).isoformat()
    return seal_snapshot(observed)


def test_packaged_rehearsal_and_real_bill_have_separate_signed_http_paths(tmp_path):
    key=generate_reviewer_key()
    db=tmp_path/"work.sqlite"
    enroll(db,"sandbox.viewer",key,"viewer","replay")
    app=create_app(db,mode="replay")
    with TestClient(app,base_url=DEFAULT_ORIGIN,client=("127.0.0.1",45001)) as client:
        assert client.get("/api/ramp/workspace").status_code == 401
        viewer=ReviewerClient(client,DEFAULT_ORIGIN,"sandbox.viewer",key)
        def read(path):
            response=client.get(path,headers=viewer.headers)
            assert response.status_code==200, response.text
            return response.json()
        work=read("/api/ramp/workspace")
        assert work["snapshot_status"]["custody"]=="packaged_receipt"
        assert next(r for r in work["resources"] if r["name"]=="agreements")["count"]==0
        assert work["source_mode"]=="REPLAY_OF_RAMP_SANDBOX"
        cap=next(r for r in work["records"] if r["finding_kind"]=="SYNTHETIC_INVOICE_CAP")
        real=next(r for r in work["records"] if r["provider_id"]==cap["provider_id"] and r["id"]!=cap["id"])
        assert real["native_status"]=="OPEN" and real["native_approval_status"]=="PENDING"
        assert real["amount"] is None and real["native_amount"]["amount_minor"]==84000
        assert cap["amount"]=="40.00" and cap["publishable"] is False and cap["actual_recovery"] is None
        detail=read("/api/ramp/records/"+real["id"])
        assert detail["native_projection"]["id"]==real["provider_id"]
        plan=read("/api/ramp/records/"+real["id"]+"/workflow")
        assert plan["delivery"]=="NOT_SENT" and plan["object_id"]==real["provider_id"]
        assert read("/api/ramp/records/"+cap["id"]+"/workflow")["status"]=="SIMULATION_ONLY"
        assert app.state.ramp_workspace.credits.summary("bears")["actual_recovery"] is None
        with pytest.raises(PermissionError):
            app.state.ramp_workspace.record_for_native("bills",real["provider_id"])


def test_import_is_scoped_immutable_and_resists_duplicate_or_older_delivery(tmp_path):
    db=tmp_path/"installed.sqlite"
    business=str(uuid4())
    desk=RampWorkspace(Workbench(db,"sandbox",tenant="copper-lab"))
    assert desk.overview()["records"]==[]
    latest,earlier=capture(),capture(-3600)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda _:desk.import_observation(latest,business),range(3)))
    assert all(r["digest"]==latest["checksum"] for r in results)
    desk.import_observation(earlier,business)
    row=desk.overview()["records"][0]
    assert len(case_versions(db,"copper-lab",row["id"]))==1
    assert desk._observation()[0]["checksum"]==latest["checksum"]
    bill=next(r for r in latest["resources"]["bills"]["records"] if r["kind"]=="bill")
    first=desk.record_for_native("bills",bill["id"])
    second=desk.record_for_native("bills",bill["id"])
    assert first["finding_digest"]==second["finding_digest"] and first["sources"]==["LIVE_RAMP_SANDBOX"]
    assert first["business_id"]==business and first["provider_id"]==bill["id"]
    with pytest.raises(ValueError):
        desk.import_observation(latest,str(uuid4()))
    corrupt=deepcopy(latest);corrupt["resources"]["bills"]["records"][0]["status"]="PAID_CHANGED"
    with pytest.raises(RampError):
        desk.import_observation(corrupt,business)
    credit=desk.credits.summary("copper-lab")
    assert credit["captured_credits"]==0 and credit["actual_recovery"] is None


def test_import_rejects_replay_and_stale_capture_for_native_delivery(tmp_path):
    bill=capture(-200000)
    ref=bill["resources"]["bills"]["records"][0]["id"]
    replay=RampWorkspace(Workbench(tmp_path/"replay.db","replay",tenant="copper-lab"))
    with pytest.raises(ValueError):
        replay.import_observation(bill,str(uuid4()))
    live=RampWorkspace(Workbench(tmp_path/"sandbox.db","sandbox",tenant="copper-lab"))
    live.import_observation(bill,str(uuid4()))
    with pytest.raises(PermissionError):
        live.record_for_native("bills",ref)
