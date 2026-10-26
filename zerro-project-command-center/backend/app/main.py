from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, SessionLocal, engine
from . import models as _registered_models
from .routers.projects import router as projects_router
from .routers.stores_exceptions import router as stores_exceptions_router
from .seed import ensure_sub_tasks, seed_database
from .vision_ticket import verify_ticket
from .sso_claims import validate_handoff_claims
from .sso_replay import consume_ticket_once
from fastapi.responses import RedirectResponse


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
        ensure_sub_tasks(db)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(projects_router)
app.include_router(stores_exceptions_router)
from .routers.phase9_finance import router as phase9_finance_router
app.include_router(phase9_finance_router)


@app.get("/health")
def health():
    return {"status": "healthy", "service": settings.app_name}



@app.post("/api/auth/sso")
def sso_exchange(request: Request, ticket: str = Form(...)):
    """Exchange cross-service ticket for host-only HttpOnly command-center session."""
    if not settings.command_center_sso_secret or not settings.command_center_expected_org:
        raise HTTPException(503, "SSO is not configured")
    try:
        claims = verify_ticket(settings.command_center_sso_secret, ticket)
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise HTTPException(401, "Invalid or expired ticket")
    try:
        safe_claims = validate_handoff_claims(claims, settings.command_center_expected_org)
    except ValueError:
        raise HTTPException(403, "Organization or entitlements not authorized")
    # A ticket can only be exchanged once across workers and deployments.
    # The unique SHA-256 digest is stored, never the bearer token itself.
    if not consume_ticket_once(ticket, claims["exp"]):
        raise HTTPException(401, "Ticket already used")
    # Only validated grants may be promoted to a Command Center session.
    from .vision_ticket import issue_ticket
    session_token = issue_ticket(settings.command_center_sso_secret, safe_claims, lifetime=3600)
    result = RedirectResponse("/", status_code=303)
    result.set_cookie("cc_session", session_token, httponly=True, secure=settings.command_center_cookie_secure,
                      samesite="lax", max_age=3600, path="/")
    result.headers["Cache-Control"] = "no-store"
    return result

@app.post("/api/auth/logout")
def sso_logout():
    result = RedirectResponse("/", status_code=303)
    result.delete_cookie("cc_session", path="/")
    return result
