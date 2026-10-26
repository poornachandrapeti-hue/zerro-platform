from datetime import date

from pydantic import Field

from app.domains.identity_projects.schemas import Strict


class DrawingIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    drawing_type: str = Field(default="General", max_length=80)
    category_id: int | None = None
    discipline_id: int
    company_id: int
    responsible_user_id: int | None = None
    reviewer_id: int | None = None
    area_id: int | None = None
    planned_date: date | None = None
    planned_submission: date | None = None
    planned_approval: date | None = None
    priority: str = "Normal"
    work_reference: str = ""
    remarks: str = ""


class DrawingUpdate(DrawingIn):
    version: int = Field(gt=0)


class PreparationIn(Strict):
    version: int = Field(gt=0)


class CommentIn(Strict):
    page_ref: str = ""
    body: str = Field(min_length=1, max_length=2000)
    severity: str = "Minor"
    stage: str = "Internal"
    owner_id: int
    due_date: date | None = None


class CancelIn(Strict):
    reason: str = Field(min_length=1)
    version: int = Field(gt=0)


class EngineeringSettingIn(Strict):
    allow_release_with_comments: bool = False


class ExternalDecisionIn(Strict):
    outcome: str
    external_reviewer: str = Field(min_length=1, max_length=200)
    reference: str = Field(min_length=1, max_length=200)
    reason: str = ""
    version: int = Field(gt=0)


class DrawingLinkIn(Strict):
    related_id: int


class CommentRespond(Strict):
    response: str = Field(min_length=1)
    version: int = Field(gt=0)


class CommentClose(Strict):
    evidence: str = Field(min_length=1)
    version: int = Field(gt=0)


class ReleaseIn(Strict):
    version: int = Field(gt=0)
    reason: str = ""


class TransmittalIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=200)
    issue_date: date
    revision_ids: list[int]
    recipient_ids: list[int]
    sender_company_id: int | None = None
    recipient_company_id: int | None = None
    expected_response: date | None = None
    method: str = ""
    external_reference: str = ""


class DispatchIn(Strict):
    version: int = Field(gt=0)


class WrenchIn(Strict):
    enabled: bool = False
    specification: str = ""
    credential_label: str = ""


class WrenchLinkIn(Strict):
    external_document_id: str = Field(min_length=1, max_length=120)
    external_revision_id: str = ""


class DisciplineIn(Strict):
    name: str = Field(min_length=1, max_length=100)


class ExtractIn(Strict):
    pages: str = Field(default="", max_length=80)


class TakeoffVersionIn(Strict):
    version: int = Field(gt=0)


class TakeoffReasonIn(Strict):
    reason: str = Field(default="", max_length=2000)
    version: int = Field(gt=0)


class TakeoffLineIn(Strict):
    description: str | None = Field(default=None, max_length=2000)
    specification: str | None = Field(default=None, max_length=2000)
    quantity: str | None = Field(default=None, max_length=30)
    unit: str | None = Field(default=None, max_length=20)
    item_id: int | None = None
    reference: str | None = Field(default=None, max_length=80)
    page: int | None = Field(default=None, ge=1)
    version: int = Field(gt=0)


class TakeoffRequirementIn(Strict):
    number: str = Field(min_length=1, max_length=80)
    company_id: int | None = None
    requested_by: int
    required_date: date
    priority: str = "Normal"
    purpose: str = Field(min_length=1, max_length=2000)
    remarks: str = ""
    version: int = Field(gt=0)
