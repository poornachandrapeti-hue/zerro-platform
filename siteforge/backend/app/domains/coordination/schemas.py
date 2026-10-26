from pydantic import Field

from app.domains.identity_projects.schemas import Strict


class ReviewerIn(Strict):
    user_id: int
    approval_limit: int | None = Field(default=None, ge=0)


class StageIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    rule: str = "all"
    quorum_count: int = 1
    reviewer_ids: list[int] = Field(default_factory=list)
    reviewers: list[ReviewerIn] = Field(default_factory=list)
    purpose: str = ""


class PolicyIn(Strict):
    record_type: str = "project.activation"
    company_id: int | None = None
    discipline_id: int | None = None
    allow_self_approval: bool = False
    stages: list[StageIn]


class DecisionIn(Strict):
    action: str
    reason: str = ""
    comment: str = ""
    version: int = Field(gt=0)


class ResubmitIn(Strict):
    version: int = Field(gt=0)


class TaskIn(Strict):
    title: str = Field(min_length=1, max_length=200)
    owner_id: int
    priority: str = "Normal"
    due_date: str | None = None


class TaskUpdate(Strict):
    status: str
    evidence: str = ""
    owner_id: int | None = None
    version: int = Field(gt=0)


class ReminderIn(Strict):
    record_type: str = "project.activation"
    reminder_hours: int = Field(ge=0, le=24 * 30)
    escalate_after_hours: int = Field(ge=0, le=24 * 30)
    recipient_ids: list[int] = Field(default_factory=list)
