"""HTTP router tests inject trusted identities. Full HMAC proof tests belong to server security."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from uptime.contracts import Principal
from uptime.correspondence_api import make_correspondence_router
from test_correspondence import Setup, REVIEWER, VIEWER, SCOPE, ID, BODIES


def test_http_claim_evidence_and_independent_correspondence(tmp_path):
    env = Setup(tmp_path / "api.db")
    context = {"person": REVIEWER, "source": Principal("bears", "status-fixture", "service")}
    app = FastAPI()
    def actor():
        if context["person"] is None:
            raise HTTPException(401)
        return context["person"]
    def reviewer():
        p = actor()
        if p.role != "reviewer":
            raise HTTPException(403)
        return p
    def guard(p):
        if p.role != "reviewer":
            raise HTTPException(403)
    def service():
        if context["source"] is None:
            raise HTTPException(401)
        return context["source"]
    app.include_router(make_correspondence_router(env.desk, actor, reviewer, guard, service))
    @app.exception_handler(PermissionError)
    def denied(request, error):
        return JSONResponse({"detail":"Denied"}, 403)
    @app.exception_handler(ValueError)
    def conflict(request, error):
        return JSONResponse({"detail":"Conflict"}, 409)
    @app.exception_handler(KeyError)
    def missing(request, error):
        return JSONResponse({"detail":"Not found"}, 404)

    with TestClient(app) as client:
        root = "/api/correspondence/claims"
        detail = root + "/" + ID
        context["person"] = None
        assert client.get(root).status_code == 401
        context["person"] = VIEWER
        assert client.get(root).status_code == 200
        assert client.post(root, json={"claim_id":"inbox-other","scope":SCOPE.model_dump()}).status_code == 403
        context["person"] = REVIEWER
        assert client.post(root, json={"claim_id":"inbox-other","scope":SCOPE.model_dump(),"entitlement":"999.00"}).status_code == 422
        assert client.post(detail + "/events", json={"event_id":"status","scope":SCOPE.model_dump(),"body":BODIES["status"]}).status_code == 200
        context["source"] = Principal("bears", "billing-fixture", "service")
        assert client.post(detail + "/events", json={"event_id":"fake-impact","scope":SCOPE.model_dump(),"body":BODIES["impact"]}).status_code == 403
        env.send("impact"); env.send("invoice")
        assert client.post(detail + "/actions/approve-claim", json={}).status_code == 200
        issued = client.post(detail + "/actions/submit-claim", json={}).json()
        assert issued["stage"] == "AWAITING_VENDOR"
        context["source"] = None
        message = {"event_id":"vendor-one","scope":SCOPE.model_dump(),"body":{"kind":"message","receipt_id":issued["submissions"][0]["id"],"text":"We need a component record."}}
        assert client.post(detail + "/events", json=message).status_code == 401
        context["source"] = Principal("bears", "vendor-fixture", "service")
        reply = client.post(detail + "/events", json=message)
        assert reply.status_code == 200 and set(reply.json()) == {"event_id","digest","received_at"}
        assert client.get(detail).json()["stage"] == "NEEDS_EVIDENCE"
        assert client.post(detail + "/actions/approve-response", json={}).status_code == 409
