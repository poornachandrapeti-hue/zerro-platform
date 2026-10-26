import hashlib, re, secrets
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError
from sqlalchemy.orm import Session
from app.db import get_db
from app.config import settings
from .models import User, LoginSession, Membership, Role, ProjectDiscipline

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(24))


def hash_token(value):
    return hashlib.sha256(value.encode()).hexdigest()


def session_cookie_name(request):
    tab = request.headers.get("x-tab-id") or ""
    if re.fullmatch(r"[A-Za-z0-9_-]{16,64}", tab):
        return f"siteforge_tab_{tab}"
    return "siteforge_session"


def verify_password(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def authenticated(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(session_cookie_name(request), "")
    session = db.get(LoginSession, hash_token(token)) if token else None
    if not session:
        raise HTTPException(401, "Authentication required")
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    user = db.get(User, session.user_id)
    if expires <= datetime.now(timezone.utc) or not user or not user.active:
        raise HTTPException(401, "Session expired or inactive account")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin not in settings.origins:
            raise HTTPException(403, "Untrusted request origin")
        csrf = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(csrf, session.csrf_token):
            raise HTTPException(403, "Invalid CSRF token")
    request.state.login_session = session
    return user


def admin(user: User = Depends(authenticated)):
    if not user.organization_admin:
        raise HTTPException(403, "Organization administrator required")
    return user


def permitted(db, user, project, action, discipline_id=None):
    if project.organization_id != user.organization_id:
        raise HTTPException(404, "Project not found")
    if user.organization_admin:
        return
    enabled = {
        x.discipline_id
        for x in db.query(ProjectDiscipline).filter_by(project_id=project.id, active=True)
    }
    if discipline_id is not None and discipline_id not in enabled:
        raise HTTPException(403, "Discipline unavailable")
    for member in db.query(Membership).filter_by(
        project_id=project.id, user_id=user.id, active=True
    ):
        role = db.get(Role, member.role_id)
        if action not in role.permissions:
            continue
        if discipline_id is None:
            return
        if member.scope == "ALL" or discipline_id in member.discipline_ids:
            return
    raise HTTPException(403, "Insufficient project permission")


def holds(db, user, project, action, discipline_id=None):
    try:
        permitted(db, user, project, action, discipline_id)
    except HTTPException:
        return False
    return True
