"""Local authenticated finance workbench. Serve through scripts/serve.py."""
from hashlib import sha256
import hmac
from pathlib import Path
import secrets
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .contracts import Principal
from .intelligence import explain
from .storage import add_session, lookup_session
from .workbench import TENANT, Workbench

ROOT=Path(__file__).resolve().parents[1]


class Empty(BaseModel):
    model_config=ConfigDict(extra="forbid")


class GuideQuery(Empty):
    case_id: str = Field(min_length=1,max_length=128)
    question: str = Field(min_length=1,max_length=1000)


class ModeRequest(Empty):
    mode: str
    cap: str


def viewer_token(secret):
    return hmac.new(secret.encode(),b"uptime-readonly-v1",sha256).hexdigest()


def create_app(db_path, *, session_secret=None, mode="replay", rehearsal=False):
    session_secret=session_secret or secrets.token_urlsafe(32)
    if len(session_secret)<24:
        raise ValueError("Use at least 24 characters of random session secret")
    if rehearsal and mode!="replay":
        raise ValueError("Scripted rehearsal requires replay mode")
    bench=Workbench(db_path,mode)
    app=FastAPI(title="Uptime for Ramp",docs_url=None,redoc_url=None,openapi_url=None)
    app.state.bench=bench

    @app.middleware("http")
    async def security(request: Request, call_next):
        if request.method=="POST":
            origin=request.headers.get("origin")
            allowed=f"{request.url.scheme}://{request.headers.get('host','')}"
            if (request.headers.get("X-Uptime-Action")!="1" or
                request.headers.get("content-type","").split(";")[0]!="application/json" or
                (origin is not None and origin!=allowed) or request.headers.get("sec-fetch-site")=="cross-site"):
                return JSONResponse({"detail":"Same-origin authenticated workbench action required"},403)
            size=request.headers.get("content-length")
            if not size or request.headers.get("transfer-encoding") or len(size)>5 or not size.isdigit() or int(size)>4096:
                return JSONResponse({"detail":"Action body too large"},413)
        response=await call_next(request)
        response.headers.update({"Cache-Control":"no-store","Referrer-Policy":"no-referrer",
                "X-Content-Type-Options":"nosniff","Content-Security-Policy":
                    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    app.add_middleware(TrustedHostMiddleware,allowed_hosts=["localhost","127.0.0.1","testserver","[::1]"])

    def actor(request: Request):
        current=lookup_session(db_path,request.cookies.get("uptime_session"),time.time())
        if not current:
            raise HTTPException(401,"Open the local sign-in link from the launcher.")
        if current.tenant != TENANT or current.role not in {"viewer","reviewer"}:
            raise HTTPException(403,"Session does not belong to this local workspace")
        return current

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

    @app.get("/session/{token}",include_in_schema=False)
    def session(token: str):
        if hmac.compare_digest(token.encode(),session_secret.encode()):
            role="reviewer"
        elif hmac.compare_digest(token.encode(),viewer_token(session_secret).encode()):
            role="viewer"
        else:
            raise HTTPException(403,"Invalid local session link")
        opaque=secrets.token_urlsafe(32)
        principal=Principal(TENANT,("scripted-test-" if rehearsal else "local-")+role,role)
        add_session(db_path,opaque,principal,time.time()+3600)
        redirect=RedirectResponse("/",303)
        redirect.set_cookie("uptime_session",opaque,httponly=True,samesite="strict",max_age=3600,
                            path="/",secure=False)  # Loopback HTTP; deployment requires TLS.
        return redirect

    @app.get("/api/dashboard")
    def dashboard(p=Depends(actor)):
        return bench.dashboard(p)

    @app.get("/api/cases/{case_id}")
    def case(case_id: str,p=Depends(actor)):
        return bench.case(p,case_id)

    @app.post("/api/cases/{case_id}/actions/{action}")
    def case_action(case_id: str,action: str,body: Empty,p=Depends(actor)):
        return bench.act(p,case_id,action)

    @app.get("/api/onboarding")
    def lab(p=Depends(actor)):
        return bench.lab(p)

    @app.post("/api/onboarding/actions/{action}")
    def lab_action(action: str,body: Empty,p=Depends(actor)):
        return bench.lab(p,action)

    @app.get("/api/policy")
    def access_policy(p=Depends(actor)):
        return bench.setting(p)

    @app.post("/api/policy")
    def change(request: ModeRequest,p=Depends(actor)):
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

    app.mount("/static",StaticFiles(directory=ROOT/"web",check_dir=False),name="static")
    return app
