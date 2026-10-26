from datetime import date
from decimal import Decimal

from pydantic import Field

from app.domains.identity_projects.schemas import Strict


class OfferIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    package_id: int
    activity_id: int | None = None


class VersionIn(Strict):
    version: int = Field(ge=1)


class CancelIn(Strict):
    reason: str = Field(min_length=3, max_length=500)
    version: int = Field(ge=1)


class DocumentIn(Strict):
    kind: str = Field(min_length=1, max_length=40)
    number: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    revision_label: str = Field(min_length=1, max_length=20)
    discipline_id: int | None = None
    company_id: int
    area_id: int | None = None
    effective_date: date | None = None
    engineering_reference: str = Field(default="", max_length=500)
    applicable_activities: str = Field(default="", max_length=2000)
    template_ids: list[int] = Field(default_factory=list, max_length=40)


class DocumentUpdate(Strict):
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    discipline_id: int | None = None
    company_id: int
    area_id: int | None = None
    effective_date: date | None = None
    engineering_reference: str = Field(default="", max_length=500)
    applicable_activities: str = Field(default="", max_length=2000)
    template_ids: list[int] = Field(default_factory=list, max_length=40)


class CheckpointIn(Strict):
    sequence: int = Field(ge=1, le=999)
    name: str = Field(min_length=1, max_length=200)
    criteria_reference: str = Field(min_length=1, max_length=500)
    responsible_parties: str = Field(min_length=1, max_length=500)
    point_type: str = Field(min_length=1, max_length=20)
    notice_hours: int = Field(default=0, ge=0, le=8760)
    required_evidence: str = Field(min_length=1, max_length=1000)
    required_signatories: str = Field(default="", max_length=500)
    partial_allowed: bool = False
    next_release_conditions: str = Field(default="", max_length=1000)


class CheckpointsIn(Strict):
    version: int = Field(ge=1)
    checkpoints: list[CheckpointIn] = Field(default_factory=list, max_length=40)


class ReviseIn(Strict):
    revision_label: str = Field(min_length=1, max_length=20)
    version: int = Field(ge=1)


class FormIn(Strict):
    discipline_id: int
    code: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    revision_label: str = Field(min_length=1, max_length=20)
    criteria_document_id: int | None = None
    units: str = Field(default="", max_length=80)
    prerequisites: str = Field(default="", max_length=2000)
    required_attachments: str = Field(default="", max_length=1000)
    items: list[str] = Field(default_factory=list, max_length=80)


class FormUpdate(Strict):
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    discipline_id: int
    criteria_document_id: int | None = None
    units: str = Field(default="", max_length=80)
    prerequisites: str = Field(default="", max_length=2000)
    required_attachments: str = Field(default="", max_length=1000)
    items: list[str] = Field(default_factory=list, max_length=80)


class DispositionIn(Strict):
    goods_receipt_line_id: int
    from_state: str = Field(min_length=1, max_length=20)
    to_state: str = Field(min_length=1, max_length=20)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    batch_number: str = Field(default="", max_length=80)
    heat_number: str = Field(default="", max_length=80)
    serial_number: str = Field(default="", max_length=80)


class MaterialIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    goods_receipt_id: int
    inspector_id: int
    requested_on: date
    inspected_on: date | None = None
    certificate_reference: str = Field(default="", max_length=200)
    findings: str = Field(default="", max_length=2000)
    lines: list[DispositionIn] = Field(min_length=1, max_length=40)


class ResultIn(Strict):
    item: str = Field(min_length=1, max_length=300)
    result: str = Field(default="", max_length=20)
    measurement: str = Field(default="", max_length=80)


class RequestIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    activity_id: int
    template_id: int
    checkpoint_id: int | None = None
    follows_id: int | None = None
    location: str = Field(min_length=1, max_length=200)
    requested_on: date
    requester_id: int
    inspector_id: int
    attendees: str = Field(default="", max_length=500)
    findings: str = Field(default="", max_length=2000)


class RequestUpdate(Strict):
    version: int = Field(ge=1)
    outcome: str = Field(min_length=1, max_length=40)
    accepted_quantity: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    location: str = Field(min_length=1, max_length=200)
    requested_on: date
    inspector_id: int
    attendees: str = Field(default="", max_length=500)
    findings: str = Field(default="", max_length=2000)
    results: list[ResultIn] = Field(min_length=1, max_length=80)


class MaterialUpdate(Strict):
    version: int = Field(ge=1)
    inspector_id: int
    requested_on: date
    inspected_on: date | None = None
    certificate_reference: str = Field(default="", max_length=200)
    findings: str = Field(default="", max_length=2000)
    lines: list[DispositionIn] = Field(min_length=1, max_length=40)


class NcrIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    source_kind: str = Field(min_length=1, max_length=20)
    source_id: int
    discipline_id: int
    company_id: int
    location: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    requirement: str = Field(min_length=3, max_length=2000)
    severity: str = Field(min_length=1, max_length=20)
    affected_scope: str = Field(min_length=3, max_length=2000)
    containment: str = Field(min_length=3, max_length=2000)
    owner_id: int
    raised_on: date
    target_on: date
    root_cause: str = Field(min_length=3, max_length=2000)
    corrective_action: str = Field(min_length=3, max_length=2000)
    disposition: str = Field(min_length=1, max_length=20)


class NcrUpdate(NcrIn):
    version: int = Field(ge=1)


class ClosureIn(Strict):
    version: int = Field(ge=1)
    evidence: str = Field(min_length=3, max_length=4000)
    verification: str = Field(min_length=3, max_length=4000)


class ConcessionIn(Strict):
    ncr_id: int
    number: str = Field(min_length=1, max_length=40)
    proposal: str = Field(min_length=3, max_length=4000)
    technical_note: str = Field(default="", max_length=2000)


class HoldIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    scope_kind: str = Field(min_length=1, max_length=20)
    scope_id: int
    checkpoint_id: int | None = None
    ncr_id: int | None = None
    owner_id: int
    reason: str = Field(min_length=3, max_length=2000)
    conditions: str = Field(min_length=3, max_length=2000)
    blocks_issue: bool = False
    blocks_work: bool = False
    blocks_handover: bool = False


class ReleaseIn(Strict):
    version: int = Field(ge=1)
    evidence: str = Field(min_length=3, max_length=4000)


class QualificationIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    person_id: int
    qualification_type: str = Field(min_length=1, max_length=120)
    applicable_activities: str = Field(min_length=1, max_length=2000)
    issuer: str = Field(min_length=1, max_length=200)
    certificate_number: str = Field(min_length=1, max_length=80)
    valid_from: date
    valid_to: date
    evidence: str = Field(min_length=3, max_length=2000)


class CalibrationIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    equipment_code: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=200)
    serial_number: str = Field(min_length=1, max_length=80)
    certificate_reference: str = Field(min_length=1, max_length=200)
    calibrated_on: date
    due_on: date
    use_range: str = Field(min_length=1, max_length=200)
    evidence: str = Field(min_length=3, max_length=2000)


class WithdrawIn(Strict):
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


class DossierIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    package_id: int


class PunchIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    package_id: int
    issue_type: str = Field(min_length=1, max_length=20)
    description: str = Field(min_length=3, max_length=4000)
    company_id: int
    owner_id: int
    severity: str = Field(min_length=1, max_length=20)
    blocking: bool = False
    due_on: date
    blocker_id: int | None = None
    activity_id: int | None = None
