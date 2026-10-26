"""Read-only ZerroBuild project master lookup. No fallback on authority failures."""
import httpx
from fastapi import HTTPException


def fetch_project_master(organization_id: str, settings) -> dict[str, dict]:
    base = settings.command_center_identity_url.rstrip("/")
    key = settings.command_center_identity_service_key
    if not base or not key:
        raise HTTPException(503, "Project authority not configured")
    try:
        org = int(organization_id)
        if org <= 0: raise ValueError("invalid org")
    except (TypeError, ValueError):
        raise HTTPException(403, "Invalid organization")
    try:
        r = httpx.get(f"{base}/api/integrations/command-center/project-master/{org}",
                      headers={"X-ZerroR-Service-Key": key}, timeout=3.0, follow_redirects=False)
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list): raise ValueError("invalid projects")
        result = {}
        for item in rows:
            if not isinstance(item, dict) or not isinstance(item.get("code"), str) or not item["code"].strip() or not isinstance(item.get("name"), str):
                raise ValueError("invalid project entry")
            code = item["code"].strip().upper()
            if code in result: raise ValueError("ambiguous project code")
            result[code] = item
        return result
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(503, "Authoritative project master unavailable")
