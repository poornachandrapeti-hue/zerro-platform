from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.domains.identity_projects.models import Audit, Project, User
from app.domains.identity_projects.security import authenticated, holds, permitted

from . import dashboard as safety_dashboard, emergency as emergency_records, environment as environment_records, field, holds as safety_holds, incidents, permits, service
from .models import (
    HseAction,
    HseAssessment,
    HseDocument,
    HseDrill,
    HseEligibility,
    HseEmergencyContact,
    HseFinding,
    HseHold,
    HseIncident,
    HseInspection,
    HseIsolation,
    HsePermit,
    HsePermitCheck,
    HseToolboxTalk,
)
from .schemas import (
    AssessmentIn,
    CheckVerifyIn,
    AckIn,
    CloseFindingIn,
    ClosePermitIn,
    ConflictRuleIn,
    CoordinationIn,
    DocumentIn,
    DrillAckIn,
    DrillIn,
    EnvironmentCriterionIn,
    EnvironmentRecordIn,
    EligibilityIn,
    EmergencyContactIn,
    EmergencyPlanIn,
    EmergencyRuleIn,
    GearIn,
    MusterIn,
    EligibilityRuleIn,
    ExtensionIn,
    FindingRuleIn,
    HandoverIn,
    InspectionIn,
    IsolationIn,
    IsolationLinkIn,
    ActionIn,
    ActionRuleIn,
    CloseActionIn,
    ConcernIn,
    EvidenceIn,
    HoldIn,
    HoldIssuerIn,
    HoldRuleIn,
    IncidentCategoryIn,
    IncidentIn,
    IncidentRuleIn,
    InvestigationIn,
    ObservationIn,
    PermitIn,
    PermitTypeIn,
    ReassessIn,
    ReasonIn,
    ScopeRuleIn,
    ToolboxIn,
    VersionIn,
    WithdrawIn,
)

router = APIRouter(prefix="/api")


def _commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate value or invalid record reference")


def _audit(db, user, action, resource, rid, project_id, details=None):
    db.add(
        Audit(
            organization_id=user.organization_id,
            actor_id=user.id,
            action=action,
            resource=resource,
            resource_id=rid,
            details=details or {},
            project_id=project_id,
        )
    )


def _project(db, user, pid):
    project = db.get(Project, pid)
    if not project or project.organization_id != user.organization_id:
        raise HTTPException(404, "Project not found")
    return project


def _view(db, user, project):
    permitted(db, user, project, "hse.view")


def _plan(db, user, project):
    permitted(db, user, project, "hse.plan")


def _either(db, user, project):
    if holds(db, user, project, "hse.edit") or holds(db, user, project, "hse.plan"):
        return
    permitted(db, user, project, "hse.edit")


@router.get("/projects/{pid}/hse")
def hse_board(pid: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return service.board(db, u, found)


@router.get("/projects/{pid}/hse/dashboard")
def hse_dashboard(
    pid: int,
    company_id: int | None = None,
    discipline_id: int | None = None,
    area_id: int | None = None,
    package_id: int | None = None,
    owner_id: int | None = None,
    severity: str = "",
    date_kind: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    u: User = Depends(authenticated),
    db: Session = Depends(get_db),
):
    found = _project(db, u, pid)
    _view(db, u, found)
    return safety_dashboard.view(
        db,
        found,
        {
            "company_id": company_id,
            "discipline_id": discipline_id,
            "area_id": area_id,
            "package_id": package_id,
            "owner_id": owner_id,
            "severity": severity,
            "date_kind": date_kind,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@router.get("/projects/{pid}/hse/work")
def hse_work(pid: int, package_id: int, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    return service.work_view(db, found, package_id)


@router.post("/projects/{pid}/hse/documents", status_code=201)
def create_document(pid: int, data: DocumentIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = service.add_document(db, u, found, data)
    _audit(db, u, "create", "hse_documents", row.id, pid, {"number": row.number})
    _commit(db)
    return service.document_view(db, u, found, row)


@router.post("/projects/{pid}/hse/documents/{document_id}/submit")
def submit_document(pid: int, document_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseDocument, document_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "HSE document not found")
    instance = service.submit_document(db, u, found, row, data.version)
    _audit(db, u, "submit", "hse_documents", row.id, pid, {"review_id": instance.id})
    _commit(db)
    view = service.document_view(db, u, found, row)
    view["review"] = {"id": instance.id, "version": instance.version}
    return view


@router.post("/projects/{pid}/hse/documents/{document_id}/resubmit")
def resubmit_document(pid: int, document_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseDocument, document_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "HSE document not found")
    instance = service._latest(db, found, service.DOCUMENT, row.id)
    if not instance:
        raise HTTPException(404, "Review not found")
    service.apply_resubmit(db, u, instance, data.version)
    _audit(db, u, "resubmit", "hse_documents", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return service.document_view(db, u, found, row)


@router.post("/projects/{pid}/hse/documents/{document_id}/withdraw")
def withdraw_document(pid: int, document_id: int, data: WithdrawIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseDocument, document_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "HSE document not found")
    service.withdraw_document(db, u, found, row, data)
    _audit(db, u, "withdraw", "hse_documents", row.id, pid, {"reason": data.reason})
    _commit(db)
    return service.document_view(db, u, found, row)


@router.post("/projects/{pid}/hse/assessments", status_code=201)
def create_assessment(pid: int, data: AssessmentIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = service.add_assessment(db, u, found, data)
    _audit(db, u, "create", "hse_assessments", row.id, pid, {"number": row.number})
    _commit(db)
    return service.assessment_view(db, u, found, row)


@router.post("/projects/{pid}/hse/assessments/{assessment_id}/submit")
def submit_assessment(pid: int, assessment_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(HseAssessment, assessment_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Risk assessment not found")
    instance = service.submit_assessment(db, u, found, row, data.version)
    _audit(db, u, "submit", "hse_assessments", row.id, pid, {"review_id": instance.id})
    _commit(db)
    view = service.assessment_view(db, u, found, row)
    view["review"] = {"id": instance.id, "version": instance.version}
    return view


@router.post("/projects/{pid}/hse/assessments/{assessment_id}/resubmit")
def resubmit_assessment(pid: int, assessment_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(HseAssessment, assessment_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Risk assessment not found")
    instance = service._latest(db, found, service.ASSESSMENT, row.id)
    if not instance:
        raise HTTPException(404, "Review not found")
    service.apply_resubmit(db, u, instance, data.version)
    _audit(db, u, "resubmit", "hse_assessments", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return service.assessment_view(db, u, found, row)


@router.post("/projects/{pid}/hse/assessments/{assessment_id}/reassess", status_code=201)
def reassess_assessment(pid: int, assessment_id: int, data: ReassessIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(HseAssessment, assessment_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Risk assessment not found")
    created = service.reassess(db, u, found, row, data)
    _audit(db, u, "reassess", "hse_assessments", created.id, pid, {"supersedes_id": row.id})
    _commit(db)
    return service.assessment_view(db, u, found, created)


@router.post("/projects/{pid}/hse/assessments/{assessment_id}/withdraw")
def withdraw_assessment(pid: int, assessment_id: int, data: WithdrawIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(HseAssessment, assessment_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Risk assessment not found")
    service.withdraw_assessment(db, u, found, row, data)
    _audit(db, u, "withdraw", "hse_assessments", row.id, pid, {"reason": data.reason})
    _commit(db)
    return service.assessment_view(db, u, found, row)


def _permit(db, pid, permit_id):
    row = db.get(HsePermit, permit_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Permit not found")
    return row


@router.post("/projects/{pid}/hse/permit-types", status_code=201)
def create_permit_type(pid: int, data: PermitTypeIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = permits.add_type(db, u, found, data)
    _audit(db, u, "create", "hse_permit_types", row.id, pid, {"name": row.name})
    _commit(db)
    return permits._type_view(row)


@router.post("/projects/{pid}/hse/permits", status_code=201)
def create_permit(pid: int, data: PermitIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = permits.add_permit(db, u, found, data)
    _audit(db, u, "create", "hse_permits", row.id, pid, {"number": row.number})
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/permits/{permit_id}/submit")
def submit_permit(pid: int, permit_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = _permit(db, pid, permit_id)
    instance = permits.submit_permit(db, u, found, row, data.version)
    _audit(db, u, "submit", "hse_permits", row.id, pid, {"review_id": instance.id})
    _commit(db)
    view = permits.permit_view(db, u, found, row)
    view["review"] = {"id": instance.id, "version": instance.version}
    return view


@router.post("/projects/{pid}/hse/permits/{permit_id}/resubmit")
def resubmit_permit(pid: int, permit_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = _permit(db, pid, permit_id)
    instance = service._latest(db, found, permits.PERMIT, row.id)
    if not instance:
        raise HTTPException(404, "Review not found")
    permits.apply_resubmit(db, u, instance, data.version)
    _audit(db, u, "resubmit", "hse_permits", row.id, pid, {"review_id": instance.id})
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/permits/{permit_id}/checks/{check_id}/verify")
def verify_permit_check(pid: int, permit_id: int, check_id: int, data: CheckVerifyIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = _permit(db, pid, permit_id)
    check = db.get(HsePermitCheck, check_id)
    if not check:
        raise HTTPException(404, "Permit check not found")
    permits.verify_check(db, u, found, row, check, data)
    _audit(db, u, "verify", "hse_permit_checks", check.id, pid, {"permit_id": row.id})
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/permits/{permit_id}/activate")
def activate_permit(pid: int, permit_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    row = _permit(db, pid, permit_id)
    permits.activate(db, u, found, row, data.version)
    _audit(db, u, "activate", "hse_permits", row.id, pid)
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/permits/{permit_id}/suspend")
def suspend_permit(pid: int, permit_id: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    row = _permit(db, pid, permit_id)
    permits.suspend(db, u, found, row, data)
    _audit(db, u, "suspend", "hse_permits", row.id, pid, {"reason": data.reason})
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/permits/{permit_id}/extend")
def extend_permit(pid: int, permit_id: int, data: ExtensionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    row = _permit(db, pid, permit_id)
    permits.extend_permit(db, u, found, row, data)
    _audit(db, u, "extend", "hse_permits", row.id, pid, {"valid_until": data.valid_until.isoformat()})
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/permits/{permit_id}/handover")
def handover_permit(pid: int, permit_id: int, data: HandoverIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = _permit(db, pid, permit_id)
    permits.handover(db, u, found, row, data)
    _audit(db, u, "handover", "hse_permits", row.id, pid)
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/permits/{permit_id}/condition-change")
def change_permit_conditions(pid: int, permit_id: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = _permit(db, pid, permit_id)
    permits.condition_change(db, u, found, row, data)
    _audit(db, u, "condition-change", "hse_permits", row.id, pid, {"reason": data.reason})
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/permits/{permit_id}/close")
def close_permit(pid: int, permit_id: int, data: ClosePermitIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = _permit(db, pid, permit_id)
    permits.close_permit(db, u, found, row, data)
    _audit(db, u, "close", "hse_permits", row.id, pid)
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/permits/{permit_id}/cancel")
def cancel_permit(pid: int, permit_id: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = _permit(db, pid, permit_id)
    permits.cancel_permit(db, u, found, row, data)
    _audit(db, u, "cancel", "hse_permits", row.id, pid, {"reason": data.reason})
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/isolations", status_code=201)
def create_isolation(pid: int, data: IsolationIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = permits.add_isolation(db, u, found, data)
    _audit(db, u, "create", "hse_isolations", row.id, pid, {"number": row.number})
    _commit(db)
    return permits.isolation_view(db, row)


@router.post("/projects/{pid}/hse/isolations/{isolation_id}/approve")
def approve_isolation(pid: int, isolation_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseIsolation, isolation_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Isolation not found")
    permits.approve_isolation(db, u, found, row, data.version)
    _audit(db, u, "approve", "hse_isolations", row.id, pid)
    _commit(db)
    return permits.isolation_view(db, row)


@router.post("/projects/{pid}/hse/isolations/{isolation_id}/remove")
def remove_isolation(pid: int, isolation_id: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(HseIsolation, isolation_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Isolation not found")
    permits.remove_isolation(db, u, found, row, data)
    _audit(db, u, "remove", "hse_isolations", row.id, pid, {"reason": data.reason})
    _commit(db)
    return permits.isolation_view(db, row)


@router.post("/projects/{pid}/hse/permits/{permit_id}/isolations")
def link_permit_isolation(pid: int, permit_id: int, data: IsolationLinkIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = _permit(db, pid, permit_id)
    isolation = db.get(HseIsolation, data.isolation_id)
    if not isolation or isolation.project_id != pid:
        raise HTTPException(404, "Isolation not found")
    permits.link_isolation(db, found, row, isolation)
    _audit(db, u, "link", "hse_permit_isolations", isolation.id, pid, {"permit_id": row.id})
    _commit(db)
    return permits.permit_view(db, u, found, row)


@router.post("/projects/{pid}/hse/conflict-rules", status_code=201)
def create_conflict_rule(pid: int, data: ConflictRuleIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = permits.add_rule(db, u, found, data)
    _audit(db, u, "create", "hse_conflict_rules", row.id, pid)
    _commit(db)
    return {"id": row.id, "require_decision": row.require_decision}


@router.post("/projects/{pid}/hse/permits/{permit_id}/coordination")
def decide_coordination(pid: int, permit_id: int, data: CoordinationIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = _permit(db, pid, permit_id)
    decided = permits.decide_conflict(db, u, found, row, data)
    _audit(db, u, "decide", "hse_coordinations", decided.id, pid)
    _commit(db)
    return permits.coordination_view(db, decided)


@router.post("/projects/{pid}/hse/eligibility-rules", status_code=201)
def create_eligibility_rule(pid: int, data: EligibilityRuleIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = field.add_eligibility_rule(db, u, found, data)
    _audit(db, u, "create", "hse_eligibility_rules", row.id, pid, {"category": row.category})
    _commit(db)
    return {"id": row.id, "category": row.category, "package_id": row.package_id, "activity_id": row.activity_id}


@router.post("/projects/{pid}/hse/eligibility", status_code=201)
def create_eligibility(pid: int, data: EligibilityIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = field.add_eligibility(db, u, found, data)
    _audit(db, u, "create", "hse_eligibility", row.id, pid, {"category": row.category})
    _commit(db)
    return field._eligibility_view(db, row)


@router.post("/projects/{pid}/hse/eligibility/{record_id}/verify")
def verify_eligibility(pid: int, record_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseEligibility, record_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Eligibility record not found")
    field.verify_eligibility(db, u, found, row, data.version)
    _audit(db, u, "verify", "hse_eligibility", row.id, pid)
    _commit(db)
    return field._eligibility_view(db, row)


@router.post("/projects/{pid}/hse/eligibility/{record_id}/withdraw")
def withdraw_eligibility(pid: int, record_id: int, data: WithdrawIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseEligibility, record_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Eligibility record not found")
    field.withdraw_eligibility(db, u, found, row, data)
    _audit(db, u, "withdraw", "hse_eligibility", row.id, pid, {"reason": data.reason})
    _commit(db)
    return field._eligibility_view(db, row)


@router.post("/projects/{pid}/hse/toolbox-rules", status_code=201)
def create_toolbox_rule(pid: int, data: ScopeRuleIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = field.add_toolbox_rule(db, u, found, data)
    _audit(db, u, "create", "hse_toolbox_rules", row.id, pid)
    _commit(db)
    return {"id": row.id, "package_id": row.package_id, "activity_id": row.activity_id}


@router.post("/projects/{pid}/hse/toolbox", status_code=201)
def create_talk(pid: int, data: ToolboxIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = field.add_talk(db, u, found, data)
    _audit(db, u, "create", "hse_toolbox_talks", row.id, pid, {"number": row.number})
    _commit(db)
    return field._talk_view(db, row)


@router.post("/projects/{pid}/hse/toolbox/{talk_id}/hold")
def hold_talk(pid: int, talk_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(HseToolboxTalk, talk_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Toolbox talk not found")
    field.hold_talk(db, row, data.version)
    _audit(db, u, "hold", "hse_toolbox_talks", row.id, pid)
    _commit(db)
    return field._talk_view(db, row)


@router.post("/projects/{pid}/hse/toolbox/{talk_id}/acknowledgments", status_code=201)
def acknowledge_talk(pid: int, talk_id: int, data: AckIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = db.get(HseToolboxTalk, talk_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Toolbox talk not found")
    field.acknowledge(db, found, row, data)
    _audit(db, u, "acknowledge", "hse_toolbox_acks", row.id, pid, {"member_id": data.member_id})
    _commit(db)
    return field._talk_view(db, row)


@router.post("/projects/{pid}/hse/finding-rules", status_code=201)
def create_finding_rule(pid: int, data: FindingRuleIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = field.add_finding_rule(db, u, found, data)
    _audit(db, u, "create", "hse_finding_rules", row.id, pid, {"severity": row.severity})
    _commit(db)
    return {"id": row.id, "severity": row.severity, "blocks_work": row.blocks_work}


@router.post("/projects/{pid}/hse/inspections", status_code=201)
def create_inspection(pid: int, data: InspectionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = field.add_inspection(db, u, found, data)
    _audit(db, u, "create", "hse_inspections", row.id, pid, {"number": row.number})
    _commit(db)
    return field._inspection_view(db, row)


@router.post("/projects/{pid}/hse/findings/{finding_id}/close")
def close_finding(pid: int, finding_id: int, data: CloseFindingIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseFinding, finding_id)
    inspection = db.get(HseInspection, row.inspection_id) if row else None
    if not row or not inspection or inspection.project_id != pid:
        raise HTTPException(404, "Finding not found")
    field.close_finding(db, u, found, row, data)
    _audit(db, u, "close", "hse_findings", row.id, pid)
    _commit(db)
    return field._finding_view(db, row)


@router.post("/projects/{pid}/hse/observations", status_code=201)
def create_observation(pid: int, data: ObservationIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    row = field.add_observation(db, u, found, data)
    _audit(db, u, "create", "hse_observations", row.id, pid, {"number": row.number})
    _commit(db)
    return field._observation_view(db, row)


@router.post("/projects/{pid}/hse/incident-categories", status_code=201)
def create_incident_category(pid: int, data: IncidentCategoryIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = incidents.add_category(db, u, found, data)
    _audit(db, u, "create", "hse_incident_categories", row.id, pid, {"name": row.name})
    _commit(db)
    return {"id": row.id, "name": row.name}


@router.post("/projects/{pid}/hse/incident-rules", status_code=201)
def create_incident_rule(pid: int, data: IncidentRuleIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = incidents.add_rule(db, u, found, data)
    _audit(db, u, "create", "hse_incident_rules", row.id, pid, {"severity": row.severity})
    _commit(db)
    return {"id": row.id, "severity": row.severity, "requires_investigation": row.requires_investigation}


@router.post("/projects/{pid}/hse/incidents", status_code=201)
def create_incident(pid: int, data: IncidentIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    row = incidents.add_incident(db, u, found, data)
    _audit(db, u, "create", "hse_incidents", row.id, pid, {"number": row.number})
    _commit(db)
    return incidents.incident_view(db, row)


@router.post("/projects/{pid}/hse/incidents/{incident_id}/investigate")
def investigate_incident(pid: int, incident_id: int, data: InvestigationIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseIncident, incident_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Incident not found")
    incidents.investigate(db, u, found, row, data)
    _audit(db, u, "investigate", "hse_incidents", row.id, pid)
    _commit(db)
    return incidents.incident_view(db, row)


@router.post("/projects/{pid}/hse/incidents/{incident_id}/submit")
def submit_incident(pid: int, incident_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseIncident, incident_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Incident not found")
    instance = incidents.submit_incident(db, u, found, row, data.version)
    _audit(db, u, "submit", "hse_incidents", row.id, pid, {"review_id": instance.id})
    _commit(db)
    view = incidents.incident_view(db, row)
    view["review"] = {"id": instance.id, "version": instance.version}
    return view


@router.post("/projects/{pid}/hse/incidents/{incident_id}/cancel")
def cancel_incident(pid: int, incident_id: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseIncident, incident_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Incident not found")
    incidents.cancel_incident(db, u, found, row, data)
    _audit(db, u, "cancel", "hse_incidents", row.id, pid)
    _commit(db)
    return incidents.incident_view(db, row)


@router.post("/projects/{pid}/hse/action-rules", status_code=201)
def save_action_rule(pid: int, data: ActionRuleIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = incidents.save_action_rule(db, u, found, data)
    _audit(db, u, "save", "hse_action_rules", row.id, pid, {"effectiveness_required": row.effectiveness_required})
    _commit(db)
    return {"id": row.id, "effectiveness_required": row.effectiveness_required}


@router.post("/projects/{pid}/hse/actions", status_code=201)
def create_action(pid: int, data: ActionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _either(db, u, found)
    row = incidents.add_action(db, u, found, data)
    _audit(db, u, "create", "hse_actions", row.id, pid, {"number": row.number})
    _commit(db)
    return incidents.action_view(db, row)


@router.post("/projects/{pid}/hse/actions/{action_id}/start")
def start_action(pid: int, action_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    row = db.get(HseAction, action_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Action not found")
    if u.id != row.owner_id:
        _either(db, u, found)
    incidents.start_action(db, u, found, row, data.version)
    _audit(db, u, "start", "hse_actions", row.id, pid)
    _commit(db)
    return incidents.action_view(db, row)


@router.post("/projects/{pid}/hse/actions/{action_id}/evidence")
def submit_action_evidence(pid: int, action_id: int, data: EvidenceIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    row = db.get(HseAction, action_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Action not found")
    incidents.submit_evidence(db, u, found, row, data)
    _audit(db, u, "evidence", "hse_actions", row.id, pid)
    _commit(db)
    return incidents.action_view(db, row)


@router.post("/projects/{pid}/hse/actions/{action_id}/close")
def close_action(pid: int, action_id: int, data: CloseActionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    row = db.get(HseAction, action_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Action not found")
    incidents.close_action(db, u, found, row, data)
    _audit(db, u, "close", "hse_actions", row.id, pid)
    _commit(db)
    return incidents.action_view(db, row)


@router.post("/projects/{pid}/hse/actions/{action_id}/cancel")
def cancel_action(pid: int, action_id: int, data: ReasonIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseAction, action_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Action not found")
    incidents.cancel_action(db, u, found, row, data)
    _audit(db, u, "cancel", "hse_actions", row.id, pid)
    _commit(db)
    return incidents.action_view(db, row)


@router.post("/projects/{pid}/hse/hold-issuers", status_code=201)
def create_hold_issuer(pid: int, data: HoldIssuerIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = safety_holds.add_issuer(db, u, found, data)
    _audit(db, u, "create", "hse_hold_issuers", row.id, pid, {"user_id": row.user_id})
    _commit(db)
    return {"id": row.id, "user_id": row.user_id}


@router.post("/projects/{pid}/hse/hold-rules", status_code=201)
def save_hold_rule(pid: int, data: HoldRuleIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = safety_holds.save_rule(db, u, found, data)
    _audit(db, u, "save", "hse_hold_rules", row.id, pid, {"separate_release": row.separate_release})
    _commit(db)
    return {"id": row.id, "separate_release": row.separate_release}


@router.post("/projects/{pid}/hse/concerns", status_code=201)
def create_concern(pid: int, data: ConcernIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    row = safety_holds.add_concern(db, u, found, data)
    _audit(db, u, "create", "hse_holds", row.id, pid, {"number": row.number})
    _commit(db)
    return safety_holds.hold_view(db, row)


@router.post("/projects/{pid}/hse/holds", status_code=201)
def create_hold(pid: int, data: HoldIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    row = safety_holds.add_hold(db, u, found, data)
    _audit(db, u, "create", "hse_holds", row.id, pid, {"number": row.number})
    _commit(db)
    return safety_holds.hold_view(db, row)


@router.post("/projects/{pid}/hse/holds/{hold_id}/release")
def request_hold_release(pid: int, hold_id: int, data: EvidenceIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    row = db.get(HseHold, hold_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Safety hold not found")
    instance = safety_holds.request_release(db, u, found, row, data)
    _audit(db, u, "submit", "hse_holds", row.id, pid, {"review_id": instance.id})
    _commit(db)
    view = safety_holds.hold_view(db, row)
    view["review"] = {"id": instance.id, "version": instance.version}
    return view


@router.post("/projects/{pid}/hse/emergency-rules", status_code=201)
def save_emergency_rule(pid: int, data: EmergencyRuleIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = emergency_records.save_rule(db, u, found, data)
    _audit(db, u, "save", "hse_emergency_rules", row.id, pid)
    _commit(db)
    return {"procedure": row.procedure, "review_days": row.review_days}


@router.post("/projects/{pid}/hse/emergency-contacts", status_code=201)
def create_emergency_contact(pid: int, data: EmergencyContactIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = emergency_records.add_contact(db, u, found, data)
    _audit(db, u, "create", "hse_emergency_contacts", row.id, pid)
    _commit(db)
    return emergency_records.contact_view(db, u, found, row)


@router.post("/projects/{pid}/hse/emergency-contacts/{contact_id}/verify")
def verify_emergency_contact(pid: int, contact_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseEmergencyContact, contact_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Emergency contact not found")
    emergency_records.verify_contact(db, u, found, row, data.version)
    _audit(db, u, "verify", "hse_emergency_contacts", row.id, pid)
    _commit(db)
    return emergency_records.contact_view(db, u, found, row)


@router.post("/projects/{pid}/hse/muster-points", status_code=201)
def create_muster_point(pid: int, data: MusterIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = emergency_records.add_muster(db, u, found, data)
    _audit(db, u, "create", "hse_muster_points", row.id, pid)
    _commit(db)
    return {"id": row.id, "name": row.name, "note": row.note}


@router.post("/projects/{pid}/hse/emergency-gear", status_code=201)
def create_emergency_gear(pid: int, data: GearIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = emergency_records.add_gear(db, u, found, data)
    _audit(db, u, "create", "hse_emergency_gear", row.id, pid)
    _commit(db)
    return {"id": row.id, "name": row.name, "location": row.location, "statement": emergency_records.GEAR_NOTE}


@router.post("/projects/{pid}/hse/emergency-plans", status_code=201)
def create_emergency_plan(pid: int, data: EmergencyPlanIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = emergency_records.add_plan(db, u, found, data)
    _audit(db, u, "create", "hse_emergency_plans", row.id, pid)
    _commit(db)
    return {"id": row.id, "number": row.number, "title": row.title}


@router.post("/projects/{pid}/hse/drills", status_code=201)
def create_drill(pid: int, data: DrillIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = emergency_records.add_drill(db, u, found, data)
    _audit(db, u, "create", "hse_drills", row.id, pid, {"number": row.number})
    _commit(db)
    return emergency_records.drill_view(db, row)


@router.post("/projects/{pid}/hse/drills/{drill_id}/hold")
def hold_drill(pid: int, drill_id: int, data: VersionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = db.get(HseDrill, drill_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Drill not found")
    emergency_records.hold_drill(db, row, data.version)
    _audit(db, u, "hold", "hse_drills", row.id, pid)
    _commit(db)
    return emergency_records.drill_view(db, row)


@router.post("/projects/{pid}/hse/drills/{drill_id}/acknowledgments", status_code=201)
def acknowledge_drill(pid: int, drill_id: int, data: DrillAckIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    row = db.get(HseDrill, drill_id)
    if not row or row.project_id != pid:
        raise HTTPException(404, "Drill not found")
    emergency_records.acknowledge(db, found, row, data)
    _audit(db, u, "acknowledge", "hse_drills", row.id, pid)
    _commit(db)
    return emergency_records.drill_view(db, row)


@router.post("/projects/{pid}/hse/environment-criteria", status_code=201)
def create_environment_criterion(pid: int, data: EnvironmentCriterionIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _plan(db, u, found)
    row = environment_records.add_criterion(db, u, found, data)
    _audit(db, u, "create", "hse_environment_criteria", row.id, pid)
    _commit(db)
    return {"id": row.id, "name": row.name, "kind": row.kind, "threshold": row.threshold}


@router.post("/projects/{pid}/hse/environment-records", status_code=201)
def create_environment_record(pid: int, data: EnvironmentRecordIn, u: User = Depends(authenticated), db: Session = Depends(get_db)):
    found = _project(db, u, pid)
    _view(db, u, found)
    row = environment_records.add_record(db, u, found, data)
    _audit(db, u, "create", "hse_environment_records", row.id, pid, {"number": row.number})
    _commit(db)
    return environment_records.record_view(db, found, row)
