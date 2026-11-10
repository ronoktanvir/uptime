"""Local authenticated finance workbench. Serve through scripts/serve.py."""
from asyncio import Lock
from contextlib import asynccontextmanager
from importlib.util import find_spec
from ipaddress import ip_address
from pathlib import Path
from re import fullmatch

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from .auth import Authority, DEFAULT_ORIGIN, TENANT

from .contracts import Principal
from .intelligence import explain
from .workbench import Workbench

ROOT=Path(__file__).resolve().parents[1]


class Empty(BaseModel):
    model_config=ConfigDict(extra="forbid")


class GuideQuery(Empty):
    case_id: str = Field(min_length=1,max_length=128)
    question: str = Field(min_length=1,max_length=1000)


class ModeRequest(Empty):
    mode: str
    cap: str


def panel_origin(value):
    """The one browser-extension origin that may frame this app in a side panel, or None.

    Framing is refused by default. An operator may name exactly one Chrome extension by its
    origin; a web origin, a wildcard, a list or anything else is refused. This changes only who
    may display the page. Sign-in and every action still require this app's own origin.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not fullmatch(r"chrome-extension://[a-p]{32}", value):
        raise ValueError("The side panel option takes exactly one chrome-extension origin.")
    return value


def create_app(db_path, *, mode="replay", rehearsal=False, approvals_enabled=False, rehearsal_secret=None,
               service_credentials=None, origin=DEFAULT_ORIGIN, tenant=TENANT, native_config=None, award_office=None,
               workflow_config=None, proposal_jobs=None, proposal_config=None, side_panel_origin=None,
               ramp_record_dirs=(), ramp_notes=None):
    if workflow_config is not None and (native_config is not None or mode != 'replay' or not rehearsal or tenant != TENANT):
        raise PermissionError('A configured local workflow requires its isolated rehearsal workspace, without a native connection.')
    frame_ancestors = panel_origin(side_panel_origin) or "'none'"
    auth = Authority(db_path, mode, rehearsal, approvals_enabled, rehearsal_secret, service_credentials, origin, tenant)
    bench = Workbench(db_path, mode) if tenant == TENANT else Workbench(db_path, mode, tenant=tenant)
    if proposal_jobs is not None and proposal_config is not None:
        raise ValueError('Select one server-side proposal configuration.')
    if proposal_config is not None:
        from .public_proposal_config import open_public_jobs
        proposal_jobs = open_public_jobs(db_path, proposal_config)

    @asynccontextmanager
    async def lifecycle(app):
        try:
            yield
        finally:
            if proposal_jobs is not None:
                proposal_jobs.close()

    app = FastAPI(title="Uptime for Ramp", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifecycle)
    app.state.bench, app.state.auth = bench, auth
    app.state.public_proposal_jobs = proposal_jobs
    write_lock = Lock()

    @app.middleware("http")
    async def security(request: Request, call_next):
        try:
            local = ip_address(request.client.host).is_loopback
        except (ValueError, AttributeError):
            local = False
        if not local or f"{request.url.scheme}://{request.headers.get('host', '')}" != auth.origin:
            return JSONResponse({"detail": "Exact local listener required"}, 400)
        if request.method == "POST":
            if (request.headers.get("X-Uptime-Action") != "1" or
                    request.headers.get("content-type", "").split(";")[0] != "application/json" or
                    request.headers.get("origin") != auth.origin or
                    request.headers.get("sec-fetch-site", "same-origin") != "same-origin"):
                return JSONResponse({"detail": "Same-origin authenticated workbench action required"}, 403)
            size = request.headers.get("content-length", "")
            large_intake = any(request.url.path == stem or request.url.path.startswith(stem + "/")
                               for stem in ("/api/v4", "/api/vendors", "/api/correspondence"))
            limit = 262144 if large_intake else 4096
            if (request.headers.get("transfer-encoding") or len(size)>6 or not size.isascii()
                    or not size.isdigit() or int(size)>limit):
                return JSONResponse({"detail": "Action body too large"}, 413)
            chunks, actual_size = [], 0
            async for chunk in request.stream():
                actual_size += len(chunk)
                if actual_size > limit or actual_size > int(size):
                    return JSONResponse({"detail": "Action body too large"}, 413)
                chunks.append(chunk)
            if actual_size != int(size):
                return JSONResponse({"detail": "Action body length mismatch"}, 413)
            # Starlette's cached Request body is replayed by call_next after bounded collection.
            request._body = b"".join(chunks)
            async with write_lock:
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff", "Cross-Origin-Opener-Policy": "same-origin",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors " + frame_ancestors
                + "; base-uri 'none'; form-action 'none'"})
        return response

    auth.register(app)
    actor = auth.actor

    def display_actor(p=Depends(actor)):
        # V3 views derive offered actions directly from this domain role.
        return p if auth.approvals_enabled else Principal(p.tenant, p.subject, "viewer")

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail":"Case not found"},404)

    @app.exception_handler(PermissionError)
    async def forbidden(request, exc):
        return JSONResponse({"detail":str(exc)},403)

    @app.exception_handler(ValueError)
    async def conflict(request, exc):
        return JSONResponse({"detail":str(exc)},409)

    @app.get("/health")
    def health():
        return {"status":"ok","mode":mode}

    @app.get("/api/dashboard")
    def dashboard(p=Depends(display_actor)):
        return bench.dashboard(p)

    @app.get("/api/cases/{case_id}")
    def case(case_id: str,p=Depends(display_actor)):
        return bench.case(p,case_id)

    @app.post("/api/cases/{case_id}/actions/{action}")
    def case_action(case_id: str,action: str,body: Empty,p=Depends(auth.reviewer)):
        return bench.act(p,case_id,action)

    @app.get("/api/onboarding")
    def lab(p=Depends(display_actor)):
        return bench.lab(p)

    @app.post("/api/onboarding/actions/{action}")
    def lab_action(action: str,body: Empty,p=Depends(auth.reviewer)):
        return bench.lab(p,action)

    @app.get("/api/policy")
    def access_policy(p=Depends(display_actor)):
        return bench.setting(p)

    @app.post("/api/policy")
    def change(request: ModeRequest,p=Depends(auth.reviewer)):
        return bench.change_setting(p,request.mode,request.cap)

    @app.get("/api/integrations")
    def integrations(p=Depends(actor)):
        return bench.integrations(p)

    @app.post("/api/guide")
    def guide(query: GuideQuery,p=Depends(actor)):
        return explain(bench.case(p,query.case_id),query.question)

    @app.get("/fixtures/pricing/agreement.json")
    def pricing_terms(p=Depends(actor)):
        return FileResponse(ROOT/"fixtures/pricing/agreement.json")

    @app.get("/fixtures/other_obligations/agreement.txt")
    def other_terms(p=Depends(actor)):
        return FileResponse(ROOT/"fixtures/other_obligations/agreement.txt")

    @app.get("/")
    def index():
        return FileResponse(ROOT/"web/index.html")

    if find_spec("uptime.v4_routes") is not None:
        from .v4_routes import register_v4_routes
        register_v4_routes(app, bench, auth,
            governing_fees=workflow_config.get('governing_fees') if workflow_config is not None else None,
            trusted_now=(lambda:app.state.workflow.now()) if workflow_config is not None else None,
            proposal_jobs=proposal_jobs)
    from .ramp_workspace import register_ramp_workspace
    native_workspace = register_ramp_workspace(app, bench, auth, award_office=award_office,
                                               ramp_record_dirs=ramp_record_dirs, ramp_notes=ramp_notes)
    if native_config is not None:
        from .ramp_native_binding import register_native_binding
        native_workspace.native_binding = register_native_binding(app, workspace=native_workspace, auth=auth, config_path=native_config)
    from .northwind_workflow import register_workspace_workflow
    register_workspace_workflow(app, bench, auth, workflow_config)
    app.mount("/static",StaticFiles(directory=ROOT/"web",check_dir=False),name="static")
    return app
