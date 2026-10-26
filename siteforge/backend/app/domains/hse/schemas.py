from datetime import date, datetime

from pydantic import Field

from app.domains.identity_projects.schemas import Strict


class DocumentIn(Strict):
    kind: str
    number: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    revision_label: str = Field(min_length=1, max_length=20)
    company_id: int
    discipline_id: int | None = None
    area_id: int | None = None
    owner_id: int
    effective_from: date | None = None
    effective_to: date | None = None
    applicability: str = ""
    engineering_reference: str = ""


class AssessmentIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    company_id: int
    discipline_id: int | None = None
    area_id: int | None = None
    package_id: int | None = None
    activity_id: int | None = None
    document_id: int | None = None
    task_description: str = Field(min_length=1)
    steps: str = ""
    hazards: str = ""
    exposed: str = ""
    existing_controls: str = ""
    initial_rating: str = Field(default="", max_length=80)
    additional_controls: str = ""
    residual_rating: str = Field(default="", max_length=80)
    control_owners: str = ""
    required_permits: str = ""
    required_competencies: str = ""
    prepared_by: int
    review_on: date | None = None


class VersionIn(Strict):
    version: int = Field(gt=0)


class WithdrawIn(Strict):
    version: int = Field(gt=0)
    reason: str = Field(min_length=3)


class ReassessIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    version: int = Field(gt=0)


class PermitTypeIn(Strict):
    name: str = Field(min_length=1, max_length=80)
    physical_required: bool = False
    handover_required: bool = False


class PermitIn(Strict):
    type_id: int
    number: str = Field(min_length=1, max_length=40)
    company_id: int
    discipline_id: int | None = None
    area_id: int | None = None
    package_id: int | None = None
    activity_id: int | None = None
    assessment_id: int | None = None
    task_description: str = Field(min_length=1)
    applicant_id: int
    performing_authority_id: int
    area_owner_id: int
    issuer_id: int
    crew_note: str = ""
    equipment_note: str = ""
    conditions: str = ""
    valid_from: datetime
    valid_until: datetime
    checks: list[str] = []
    external_reference: str = ""
    external_evidence: str = ""


class CheckVerifyIn(Strict):
    evidence: str = Field(min_length=1)
    acknowledged: bool = True


class ReasonIn(Strict):
    version: int = Field(gt=0)
    reason: str = Field(min_length=3)


class ExtensionIn(Strict):
    version: int = Field(gt=0)
    valid_until: datetime
    reason: str = Field(min_length=3)


class HandoverIn(Strict):
    version: int = Field(gt=0)
    performing_authority_id: int
    reason: str = Field(min_length=3)


class ClosePermitIn(Strict):
    version: int = Field(gt=0)
    work_status: str = Field(min_length=3)
    site_condition: str = Field(min_length=3)


class IsolationIn(Strict):
    kind: str
    number: str = Field(min_length=1, max_length=40)
    authority_id: int
    area_id: int | None = None
    evidence: str = ""
    allow_removal_with_active_permit: bool = False
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class IsolationLinkIn(Strict):
    isolation_id: int


class ConflictRuleIn(Strict):
    type_a_id: int
    type_b_id: int
    same_area: bool = True
    require_decision: bool = True
    note: str = ""


class CoordinationIn(Strict):
    other_permit_id: int
    decision: str = Field(min_length=3)
    controls: str = Field(min_length=3)


class ScopeRuleIn(Strict):
    package_id: int | None = None
    activity_id: int | None = None


class EligibilityRuleIn(ScopeRuleIn):
    category: str = Field(min_length=1, max_length=80)


class EligibilityIn(Strict):
    member_id: int
    category: str = Field(min_length=1, max_length=80)
    evidence: str = Field(min_length=3)
    expires_on: date | None = None


class ToolboxIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    talk_on: date
    shift: str = Field(default="", max_length=40)
    company_id: int
    area_id: int | None = None
    package_id: int | None = None
    activity_id: int | None = None
    topic: str = Field(min_length=1)
    assessment_id: int | None = None
    permit_id: int | None = None
    presenter_id: int
    issues: str = ""
    follow_up: str = ""
    attachment_reference: str = ""


class AckIn(Strict):
    member_id: int
    evidence: str = Field(min_length=3)


class FindingIn(Strict):
    description: str = Field(min_length=3)
    severity: str = Field(min_length=1, max_length=80)
    owner_id: int
    target_on: date | None = None
    action: str = ""
    photo_reference: str = ""


class InspectionIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    inspection_type: str
    company_id: int
    discipline_id: int | None = None
    area_id: int | None = None
    package_id: int | None = None
    activity_id: int | None = None
    inspector_id: int
    inspected_on: date
    checklist_document_id: int | None = None
    findings: list[FindingIn] = []


class FindingRuleIn(Strict):
    severity: str = Field(min_length=1, max_length=80)
    blocks_work: bool = False


class CloseFindingIn(Strict):
    version: int = Field(gt=0)
    evidence: str = Field(min_length=3)


class ObservationIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    observation_type: str
    description: str = Field(min_length=3)
    area_id: int | None = None
    package_id: int | None = None
    activity_id: int | None = None
    evidence: str = ""


class IncidentCategoryIn(Strict):
    name: str = Field(min_length=1, max_length=80)


class IncidentRuleIn(Strict):
    severity: str = Field(min_length=1, max_length=80)
    requires_investigation: bool = False


class IncidentIn(Strict):
    category_id: int
    number: str = Field(min_length=1, max_length=40)
    event_at: datetime
    timezone_name: str = Field(min_length=1, max_length=64)
    area_id: int | None = None
    location: str = ""
    company_id: int
    package_id: int | None = None
    activity_id: int | None = None
    involved: str = ""
    description: str = Field(min_length=3)
    immediate_actions: str = ""
    emergency_requested: bool = False
    initial_severity: str = Field(default="", max_length=80)
    evidence: str = ""


class InvestigationIn(Strict):
    version: int = Field(gt=0)
    verified_classification: str = Field(min_length=1, max_length=80)
    contributing_factors: str = ""
    root_causes: str = ""
    lessons: str = ""
    team_ids: list[int] = []


class ActionRuleIn(Strict):
    effectiveness_required: bool = False


class ActionIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=3)
    severity: str = Field(default="", max_length=80)
    company_id: int
    owner_id: int
    verifier_id: int
    due_on: date | None = None
    interim_controls: str = ""
    source_type: str = ""
    source_id: int | None = None


class EvidenceIn(Strict):
    version: int = Field(gt=0)
    evidence: str = Field(min_length=3)


class CloseActionIn(Strict):
    version: int = Field(gt=0)
    effectiveness: str = ""


class HoldIssuerIn(Strict):
    user_id: int


class HoldRuleIn(Strict):
    separate_release: bool = False


class ConcernIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    company_id: int
    reason: str = Field(min_length=3)
    severity: str = Field(default="", max_length=80)
    package_id: int | None = None
    area_id: int | None = None


class EmergencyRuleIn(Strict):
    procedure: str = ""
    review_days: int | None = Field(default=None, ge=1, le=3650)


class EmergencyContactIn(Strict):
    contact_id: int
    response_role: str = Field(min_length=1, max_length=80)


class MusterIn(Strict):
    name: str = Field(min_length=1, max_length=80)
    area_id: int | None = None
    note: str = ""


class GearIn(Strict):
    name: str = Field(min_length=1, max_length=80)
    area_id: int | None = None
    location: str = Field(min_length=3)


class EmergencyPlanIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    engineering_reference: str = ""
    document_id: int | None = None


class DrillIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    planned_on: date
    findings: str = ""


class DrillAckIn(Strict):
    member_id: int
    evidence: str = Field(min_length=1)


class EnvironmentCriterionIn(Strict):
    name: str = Field(min_length=1, max_length=80)
    kind: str = ""
    threshold: str = Field(min_length=3)


class EnvironmentRecordIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    kind: str
    description: str = Field(min_length=3)
    recorded_on: date
    area_id: int | None = None
    package_id: int | None = None
    criterion_id: int | None = None
    reading: str = ""
    result: str = "Not assessed"
    evidence: str = ""
    action_id: int | None = None


class HoldIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    company_id: int
    owner_id: int
    reason: str = Field(min_length=3)
    source: str = Field(min_length=1, max_length=80)
    severity: str = Field(default="", max_length=80)
    scope_kind: str
    package_id: int | None = None
    activity_id: int | None = None
    area_id: int | None = None
    equipment_note: str = ""
    affected_work: str = ""
    restricted_actions: str = Field(min_length=3)
    immediate_controls: str = ""
    release_conditions: str = Field(min_length=3)
