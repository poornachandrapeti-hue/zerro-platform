"""Fail-closed Phase 3 read-only authorization for SiteForge project memberships."""
from dataclasses import dataclass
import json
from fastapi import HTTPException, Request
from sqlalchemy import select
from .config import get_settings
from .vision_ticket import verify_ticket
from .database import SessionLocal
from .models import Project, Discipline
from .project_identity import load_project_mapping, to_command_center_code
from .live_permissions import refresh_live_grants

@dataclass(frozen=True)
class CurrentUser:
    role: str
    discipline: str | None
    grants: tuple
    project_code: str | None = None
    discipline_codes: frozenset[str] = frozenset()


def get_current_user(request: Request) -> CurrentUser:
    settings = get_settings()
    if not settings.command_center_sso_secret or not settings.command_center_expected_org:
        raise HTTPException(503, "SSO and organization binding must be configured")
    try:
        claims = verify_ticket(settings.command_center_sso_secret, request.cookies.get("cc_session", ""))
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise HTTPException(401, "Sign in through ZerroBuild")
    if str(claims.get("org")) != settings.command_center_expected_org or not claims.get("sub") or claims.get("role") != "VIEWER":
        raise HTTPException(403, "Organization or role denied")
    # Refresh from ZerroBuild on every protected request. Fail closed on errors.
    claims = refresh_live_grants(claims, settings)
    grants = claims.get("grants")
    if not isinstance(grants, list) or len(grants) > 1000:
        raise HTTPException(403, "Missing project entitlements")
    # Until centralized revocation and record-level authorization are available, disable all Command Center writes.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        raise HTTPException(403, "Command Center is read-only under SiteForge RBAC")
    try:
        project_map = load_project_mapping(settings.command_center_project_map)
    except (ValueError, TypeError):
        raise HTTPException(503, "Invalid project map")
    try:
        discipline_map = json.loads(settings.command_center_discipline_map)
        if not isinstance(discipline_map, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in discipline_map.items()):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(503, "Invalid discipline map")
    mapped = {}
    for g in grants:
        if not isinstance(g, dict) or not isinstance(g.get("code"), str) or not isinstance(g.get("discipline_ids"), list):
            raise HTTPException(403, "Invalid project entitlements")
        cc_code = to_command_center_code(g["code"], project_map)
        if cc_code:
            # Fail closed for malformed or missing source discipline identities.
            names = g.get("discipline_names", {})
            if not isinstance(names, dict):
                raise HTTPException(403, "Invalid discipline entitlements")
            if g.get("full_scope") is not True and any(str(i) not in names for i in g["discipline_ids"]):
                raise HTTPException(403, "Incomplete discipline entitlements")
            allowed = {discipline_map[names[str(i)]] for i in g["discipline_ids"] if str(i) in names and names[str(i)] in discipline_map}
            g = {**g, "cc_disciplines": sorted(allowed)}
            mapped[cc_code] = g
    parts = request.url.path.strip("/").split("/")
    # Only approved read endpoints; block global contractor directory and unknown endpoints.
    if parts == ["api", "projects"]:
        return CurrentUser("VIEWER", None, tuple(mapped.items()))
    if len(parts) in (4, 5) and parts[:2] == ["api", "projects"] and parts[2].isdigit():
        with SessionLocal() as db:
            p = db.get(Project, int(parts[2]))
            if not p or p.code not in mapped:
                raise HTTPException(404, "Project not found")
            g = mapped[p.code]
            # All existing detail outputs contain commercial data: require the source permission.
            if not g.get("commercial"):
                raise HTTPException(403, "Commercial reporting permission required")
            codes = frozenset(g["cc_disciplines"])
            # An org-wide/all-discipline grant is only valid when its mapped list covers
            # every Command Center discipline in the specific project.
            actual_codes = {x.code for x in db.scalars(select(Discipline).where(Discipline.project_id == p.id))}
            if not codes or not codes.issubset(actual_codes):
                raise HTTPException(403, "Missing or invalid project discipline mapping")
            if g.get("full_scope") and codes != actual_codes:
                raise HTTPException(403, "Incomplete full-project discipline mapping")
            if len(parts) == 4 and parts[3] in ("dashboard", "live-progress", "planning-monitor", "financial-monitoring", "contract-intelligence", "stores-phase8-exceptions"):
                return CurrentUser("VIEWER", None, ((p.code, g),), p.code, codes)
            if len(parts) == 4 and parts[3] == "dashboard":
                return CurrentUser("VIEWER", None, ((p.code, g),), p.code, codes)
            if len(parts) == 5 and parts[3] == "disciplines" and parts[4].upper() in codes:
                return CurrentUser("VIEWER", None, ((p.code, g),), p.code, codes)
    raise HTTPException(403, "Resource not authorized")


def ensure_discipline_access(user: CurrentUser, discipline_code: str) -> None:
    if discipline_code.upper() not in user.discipline_codes:
        raise HTTPException(403, "Discipline not authorized")
