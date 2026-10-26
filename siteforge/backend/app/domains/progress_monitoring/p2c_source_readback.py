"""P2C1: authorized, read-only Construction and QA source candidates.

A candidate is NOT a source link. Linking and accepted progress stay blocked
until an independent, persisted binding and reviewer authorization exist.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.construction.models import ProgressReport, ProgressLine, ConstructionActivity
from app.domains.quality.models import ConstructionRequest
from .router import progress_scope

router = APIRouter(prefix="/api/projects/{pid}/progress/source-candidates", tags=["Progress Source Candidates"])


def allowed(company_id, discipline_id, scope):
    if scope["all"]:
        return True
    if company_id is None or discipline_id is None:
        return False
    return any(company_id == company and (not disciplines or discipline_id in disciplines)
               for company, disciplines in scope["pairs"])


def candidate_status(report, line, qa):
    """Present provenance; never infer a binding from activity matching."""
    return {"construction_approved": report.status == "Approved",
            "inspection_approved": qa.status == "Approved",
            "inspection_accepted": qa.outcome in ("Accepted", "Partially Accepted"),
            "same_activity": line.activity_id == qa.activity_id,
            "link_verified": False, "eligible_for_earned_progress": False,
            "billing_certified": False,
            "reason": "Activity match is a candidate only; verified line-to-inspection binding required"}


@router.get("/construction/{line_id}")
def construction_candidate(pid: int, line_id: int, user: User = Depends(authenticated),
                           db: Session = Depends(get_db)):
    scope = progress_scope(db, user, pid)
    line = db.get(ProgressLine, line_id)
    if line is None:
        raise HTTPException(404, "Construction progress line not found")
    report = db.query(ProgressReport).filter_by(id=line.report_id,
          organization_id=user.organization_id, project_id=pid).first()
    if report is None or not allowed(report.company_id, report.discipline_id, scope):
        raise HTTPException(404, "Construction progress line not found")
    activity = db.query(ConstructionActivity).filter_by(id=line.activity_id,
        organization_id=user.organization_id, project_id=pid).first()
    if activity is None or activity.company_id != report.company_id or activity.discipline_id != report.discipline_id:
        raise HTTPException(409, "Construction activity scope mismatch")
    return {"report_id": report.id, "line_id": line.id, "activity_id": line.activity_id,
            "report_status": report.status, "company_id": report.company_id,
            "discipline_id": report.discipline_id,
            "reported_quantity": str(line.quantity) if line.quantity is not None else None,
            "source_type": "construction.progress_line", "link_verified": False,
            "eligible_for_earned_progress": False, "billing_certified": False}


@router.get("/qa/{inspection_id}")
def qa_candidate(pid: int, inspection_id: int, user: User = Depends(authenticated),
                 db: Session = Depends(get_db)):
    scope = progress_scope(db, user, pid)
    row = db.query(ConstructionRequest).filter_by(id=inspection_id,
          organization_id=user.organization_id, project_id=pid).first()
    if row is None:
        raise HTTPException(404, "QA inspection not found")
    activity = db.query(ConstructionActivity).filter_by(id=row.activity_id,
          organization_id=user.organization_id, project_id=pid).first()
    if activity is None or activity.company_id != row.company_id or not allowed(
            activity.company_id, activity.discipline_id, scope):
        raise HTTPException(404, "QA inspection not found")
    if activity.package_id != row.package_id:
        raise HTTPException(409, "QA package mismatch")
    return {"inspection_id": row.id, "activity_id": row.activity_id,
            "inspection_status": row.status, "outcome": row.outcome,
            "company_id": row.company_id, "discipline_id": activity.discipline_id,
            "accepted_quantity": str(row.accepted_quantity) if row.accepted_quantity is not None else None,
            "source_type": "quality.construction_request", "link_verified": False,
            "eligible_for_earned_progress": False, "billing_certified": False}
