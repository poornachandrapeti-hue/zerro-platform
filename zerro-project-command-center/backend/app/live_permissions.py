"""Request-time project entitlement verification against the SiteForge authority."""
import httpx
from fastapi import HTTPException
from .sso_claims import validate_handoff_claims


def refresh_live_grants(session_claims: dict, settings) -> dict:
    base = settings.command_center_identity_url.rstrip("/")
    key = settings.command_center_identity_service_key
    if not base or not key:
        raise HTTPException(503, "Live authorization not configured")
    try:
        uid = int(session_claims["sub"])
        if uid <= 0:
            raise ValueError("Bad subject")
    except (ValueError, TypeError, KeyError):
        raise HTTPException(401, "Invalid session subject")
    try:
        response = httpx.get(
            f"{base}/api/integrations/command-center/live-grants/{uid}",
            headers={"X-ZerroR-Service-Key": key},
            timeout=2.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        live = validate_handoff_claims(response.json(), settings.command_center_expected_org)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise HTTPException(503, "Unable to verify current project permissions")
    if live["sub"] != str(session_claims["sub"]) or live["org"] != str(session_claims["org"]):
        raise HTTPException(403, "Identity is no longer authorized")
    # Never trust stale grants stored in the session; replace with the current authority.
    return live
