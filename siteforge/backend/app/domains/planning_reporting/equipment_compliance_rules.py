"""E5 compliance guardrails; evidence is internal, not external certification verification."""
from datetime import date, timezone
from fastapi import HTTPException

VALID_KINDS = ('Calibration', 'Certification', 'Inspection')

def ensure_compliant(asset, certificates, holds, through_date: date):
    """Fail closed on every recorded mandatory certificate and all active safety holds.

    Absence of a certificate is NOT proof of compliance. The existing inspection
    requirement remains mandatory for individual equipment. Mandatory categories
    are declared in asset.operating_specs['required_certificates'] when configured.
    """
    if any(h.status == 'Active' for h in holds):
        raise HTTPException(409, 'Active safety hold prevents equipment use')
    required = (getattr(asset, 'operating_specs', None) or {}).get('required_certificates', [])
    if not isinstance(required, list) or any(k not in VALID_KINDS for k in required):
        raise HTTPException(409, 'Invalid mandatory certification configuration')
    for kind in required:
        eligible = [c for c in certificates if c.kind == kind and c.status == 'Verified'
                    and c.valid_through >= through_date]
        if not eligible:
            raise HTTPException(409, f'{kind} verification missing or expired')
    for c in certificates:
        if c.required and (c.status != 'Verified' or c.valid_through < through_date):
            raise HTTPException(409, f'Required {c.kind} evidence not verified for use window')
    return True

def review_allowed(evidence, reviewer_id, decision):
    if decision not in ('Verified', 'Rejected'):
        raise HTTPException(422, 'Decision must be Verified or Rejected')
    if evidence.status != 'Pending':
        raise HTTPException(409, 'Only pending evidence may be reviewed')
    if evidence.created_by == reviewer_id:
        raise HTTPException(403, 'Independent certificate reviewer required')
    return True

def release_allowed(hold, actor_id, evidence_ref):
    if hold.status != 'Active':
        raise HTTPException(409, 'Hold has already been released')
    if hold.created_by == actor_id:
        raise HTTPException(403, 'Hold creator cannot independently release')
    if not evidence_ref or len(evidence_ref.strip()) < 3:
        raise HTTPException(422, 'Release evidence is required')
    return True
