"""Planning execution structures; project and work packages stay owned by their existing domains."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, ForeignKey, JSON, Text, Numeric, UniqueConstraint
from app.db import Base

def utcnow(): return datetime.now(timezone.utc)

class PlanningWBS(Base):
    __tablename__ = 'planning_wbs'
    __table_args__ = (UniqueConstraint('project_id','code', name='uq_planning_wbs_project_code'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    code = Column(String(80), nullable=False)
    name = Column(String(200), nullable=False)
    parent_id = Column(Integer, ForeignKey('planning_wbs.id'), nullable=True)
    description = Column(Text, nullable=False, default='')
    company_id = Column(Integer, nullable=True)
    discipline_id = Column(Integer, nullable=True)
    location_id = Column(Integer, nullable=True)
    owner_id = Column(Integer, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

class PlanningCalendar(Base):
    __tablename__ = 'planning_calendars'
    __table_args__ = (UniqueConstraint('project_id','code', name='uq_planning_calendar_project_code'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    code = Column(String(80), nullable=False)
    name = Column(String(200), nullable=False)
    timezone = Column(String(100), nullable=False)
    working_days = Column(JSON, nullable=False)
    shift_start = Column(String(5), nullable=False)
    shift_end = Column(String(5), nullable=False)
    holidays = Column(JSON, nullable=False, default=list)
    version = Column(Integer, nullable=False, default=1)

class PlanningSchedule(Base):
    __tablename__ = 'planning_schedules'
    __table_args__ = (UniqueConstraint('project_id','name','version', name='uq_planning_schedule_version'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    kind = Column(String(30), nullable=False)
    version = Column(String(50), nullable=False)
    data_date = Column(Date, nullable=False)
    calendar_id = Column(Integer, ForeignKey('planning_calendars.id'), nullable=False)
    owner_id = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default='Draft')
    description = Column(Text, nullable=False, default='')
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

class PlanningActivity(Base):
    __tablename__ = 'planning_activities'
    __table_args__ = (UniqueConstraint('schedule_id','code', name='uq_planning_activity_schedule_code'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey('planning_schedules.id'), nullable=False, index=True)
    wbs_id = Column(Integer, ForeignKey('planning_wbs.id'), nullable=False)
    calendar_id = Column(Integer, ForeignKey('planning_calendars.id'), nullable=False)
    code = Column(String(80), nullable=False)
    name = Column(String(240), nullable=False)
    activity_type = Column(String(20), nullable=False)
    company_id = Column(Integer, nullable=False)
    discipline_id = Column(Integer, nullable=True)
    owner_id = Column(Integer, nullable=True)
    location_id = Column(Integer, nullable=True)
    duration_hours = Column(Integer, nullable=True)
    planned_start = Column(Date, nullable=True)
    planned_finish = Column(Date, nullable=True)
    progress_method = Column(String(30), nullable=True)
    source_type = Column(String(60), nullable=True)
    source_id = Column(String(100), nullable=True)
    remarks = Column(Text, nullable=False, default='')

class PlanningDependency(Base):
    __tablename__='planning_dependencies'
    __table_args__=(UniqueConstraint('schedule_id','predecessor_id','successor_id',name='uq_planning_dep_pair'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    schedule_id=Column(Integer,ForeignKey('planning_schedules.id'),nullable=False,index=True)
    predecessor_id=Column(Integer,ForeignKey('planning_activities.id'),nullable=False)
    successor_id=Column(Integer,ForeignKey('planning_activities.id'),nullable=False)
    relation=Column(String(2),nullable=False,default='FS')
    lag_hours=Column(Integer,nullable=False,default=0)


class PlanningPublication(Base):
    """Immutable schedule snapshot: published revision is never updated in-place."""
    __tablename__ = 'planning_publications'
    __table_args__ = (UniqueConstraint('schedule_id', 'revision', name='uq_planning_pub_revision'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey('planning_schedules.id'), nullable=False, index=True)
    revision = Column(String(80), nullable=False)
    status = Column(String(30), nullable=False, default='Pending Review')
    reason = Column(Text, nullable=False)
    snapshot = Column(JSON, nullable=False)
    submitted_by = Column(Integer, nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewed_by = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    decision_note = Column(Text, nullable=True)
    is_current = Column(Boolean, nullable=False, default=False)


class PlanningPeriodTarget(Base):
    """Targets are immutable after approval; percentages use explicit approved leaf weights."""
    __tablename__='planning_period_targets'
    __table_args__=(UniqueConstraint('publication_id','activity_id','period_end',name='uq_planning_period_target'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    project_id=Column(Integer,nullable=False,index=True)
    publication_id=Column(Integer,ForeignKey('planning_publications.id'),nullable=False,index=True)
    activity_id=Column(Integer,nullable=False)
    period_end=Column(Date,nullable=False)
    cumulative_percent=Column(Integer,nullable=False)
    weight_basis_points=Column(Integer,nullable=False)
    created_by=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)

class PlanningProgressCapture(Base):
    """A sample of CURRENT source values captured at a known instant, not historical replay."""
    __tablename__='planning_progress_captures'
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    project_id=Column(Integer,nullable=False,index=True)
    publication_id=Column(Integer,ForeignKey('planning_publications.id'),nullable=False,index=True)
    captured_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)
    captured_by=Column(Integer,nullable=False)
    snapshot=Column(JSON,nullable=False)


class PlanningLookahead(Base):
    __tablename__='planning_lookaheads'
    __table_args__=(UniqueConstraint('project_id','code',name='uq_lookahead_project_code'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    code=Column(String(80),nullable=False)
    schedule_id=Column(Integer,ForeignKey('planning_schedules.id'),nullable=False)
    horizon=Column(String(12),nullable=False)
    start_date=Column(Date,nullable=False)
    end_date=Column(Date,nullable=False)
    status=Column(String(20),nullable=False,default='Draft')
    created_by=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)

class PlanningLookaheadItem(Base):
    __tablename__='planning_lookahead_items'
    __table_args__=(UniqueConstraint('lookahead_id','activity_id',name='uq_lookahead_activity'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    lookahead_id=Column(Integer,ForeignKey('planning_lookaheads.id'),nullable=False,index=True)
    activity_id=Column(Integer,ForeignKey('planning_activities.id'),nullable=False)
    target_date=Column(Date,nullable=False)
    target_quantity=Column(Integer,nullable=True)
    target_unit=Column(String(40),nullable=True)
    owner_id=Column(Integer,nullable=False)
    commitment=Column(String(20),nullable=False,default='Pending')
    readiness=Column(String(20),nullable=False,default='Unknown')
    readiness_notes=Column(Text,nullable=False,default='')
    blocker=Column(Text,nullable=False,default='')
    resolution_owner_id=Column(Integer,nullable=True)
    resolution_due=Column(Date,nullable=True)
    achieved_quantity=Column(Integer,nullable=True)
    variance_reason=Column(Text,nullable=False,default='')
    updated_by=Column(Integer,nullable=False)
    updated_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)


class PlanningResourceDemand(Base):
    __tablename__='planning_resource_demands'
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    schedule_id=Column(Integer,ForeignKey('planning_schedules.id'),nullable=False,index=True)
    activity_id=Column(Integer,ForeignKey('planning_activities.id'),nullable=False,index=True)
    period_start=Column(Date,nullable=False)
    period_end=Column(Date,nullable=False)
    resource_type=Column(String(20),nullable=False)
    resource_name=Column(String(160),nullable=False)
    company_id=Column(Integer,nullable=True)
    demand_quantity=Column(Integer,nullable=False)
    demand_unit=Column(String(20),nullable=False)
    confirmed_capacity=Column(Integer,nullable=True)
    capacity_source=Column(String(200),nullable=True)
    notes=Column(Text,nullable=False,default='')
    created_by=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)

class PlanningRecoveryScenario(Base):
    __tablename__='planning_recovery_scenarios'
    __table_args__=(UniqueConstraint('project_id','code',name='uq_planning_recovery_code'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    schedule_id=Column(Integer,ForeignKey('planning_schedules.id'),nullable=False,index=True)
    code=Column(String(80),nullable=False)
    title=Column(String(200),nullable=False)
    reason=Column(Text,nullable=False)
    proposed_changes=Column(Text,nullable=False)
    schedule_impact_days=Column(Integer,nullable=True)
    resource_impact=Column(Text,nullable=False,default='')
    cost_impact_reference=Column(String(200),nullable=True)
    required_reviews=Column(JSON,nullable=False,default=list)
    status=Column(String(20),nullable=False,default='Draft')
    created_by=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)


class PlanningRecoveryReview(Base):
    __tablename__='planning_recovery_reviews'
    id=Column(Integer,primary_key=True)
    scenario_id=Column(Integer,ForeignKey('planning_recovery_scenarios.id'),nullable=False,index=True)
    organization_id=Column(Integer,nullable=False)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False)
    department=Column(String(60),nullable=False)
    decision=Column(String(20),nullable=False)
    comment=Column(Text,nullable=False,default='')
    actor_id=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)

class PlanningRecoveryEvent(Base):
    __tablename__='planning_recovery_events'
    id=Column(Integer,primary_key=True)
    scenario_id=Column(Integer,ForeignKey('planning_recovery_scenarios.id'),nullable=False,index=True)
    organization_id=Column(Integer,nullable=False)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False)
    previous_status=Column(String(30),nullable=True)
    next_status=Column(String(30),nullable=False)
    action=Column(String(40),nullable=False)
    comment=Column(Text,nullable=False,default='')
    actor_id=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)


class PlanningAlert(Base):
    __tablename__='planning_alerts'
    __table_args__=(UniqueConstraint('project_id','dedupe_key',name='uq_planning_alert_dedupe'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    dedupe_key=Column(String(180),nullable=False)
    trigger_type=Column(String(50),nullable=False)
    source_type=Column(String(50),nullable=False)
    source_id=Column(Integer,nullable=False)
    title=Column(String(250),nullable=False)
    description=Column(Text,nullable=False,default='')
    severity=Column(String(12),nullable=False,default='Warning')
    owner_id=Column(Integer,nullable=True)
    status=Column(String(20),nullable=False,default='Open')
    first_detected_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)
    last_detected_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)
    acknowledged_by=Column(Integer,nullable=True)
    acknowledged_at=Column(DateTime(timezone=True),nullable=True)
    resolved_by=Column(Integer,nullable=True)
    resolved_at=Column(DateTime(timezone=True),nullable=True)
    resolution_note=Column(Text,nullable=False,default='')

class PlanningAlertEvent(Base):
    __tablename__='planning_alert_events'
    id=Column(Integer,primary_key=True)
    alert_id=Column(Integer,ForeignKey('planning_alerts.id'),nullable=False,index=True)
    organization_id=Column(Integer,nullable=False)
    project_id=Column(Integer,nullable=False)
    actor_id=Column(Integer,nullable=False)
    action=Column(String(30),nullable=False)
    note=Column(Text,nullable=False,default='')
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)


class PlanningMilestoneEvidence(Base):
    """Independent-reviewed evidence of an actual milestone achievement date."""
    __tablename__ = 'planning_milestone_evidence'
    __table_args__ = (UniqueConstraint('publication_id', 'activity_code', name='uq_planning_milestone_evidence'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    publication_id = Column(Integer, ForeignKey('planning_publications.id'), nullable=False, index=True)
    activity_code = Column(String(80), nullable=False)
    achieved_on = Column(Date, nullable=False)
    evidence_ref = Column(String(240), nullable=False)
    submitted_by = Column(Integer, nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    status = Column(String(24), nullable=False, default='Pending Review')
    reviewed_by = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=False, default='')

class PlanningResourceAllocation(Base):
    """Draft allocation evidence. Not an authoritative HR shift or equipment reservation."""
    __tablename__='planning_resource_allocations'
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    schedule_id=Column(Integer,ForeignKey('planning_schedules.id'),nullable=False,index=True)
    activity_id=Column(Integer,ForeignKey('planning_activities.id'),nullable=False,index=True)
    resource_type=Column(String(20),nullable=False)
    resource_ref=Column(String(120),nullable=False)
    company_id=Column(Integer,nullable=True)
    starts_at=Column(DateTime(timezone=True),nullable=False)
    ends_at=Column(DateTime(timezone=True),nullable=False)
    status=Column(String(20),nullable=False,default='Proposed')
    notes=Column(Text,nullable=False,default='')
    created_by=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)
    reviewed_by=Column(Integer,nullable=True)
    reviewed_at=Column(DateTime(timezone=True),nullable=True)
    review_note=Column(Text,nullable=False,default='')

class PlanningEquipmentAsset(Base):
    """Organization equipment identity and current inspection evidence; not a statutory certificate store."""
    __tablename__ = 'planning_equipment_assets'
    __table_args__ = (UniqueConstraint('organization_id','asset_code',name='uq_planning_equipment_asset_code'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    asset_code=Column(String(100),nullable=False)
    name=Column(String(200),nullable=False)
    equipment_type=Column(String(100),nullable=False)
    status=Column(String(30),nullable=False,default='Active')
    inspection_valid_through=Column(Date,nullable=True)
    inspection_evidence_ref=Column(String(240),nullable=True)
    inspection_review_status=Column(String(20),nullable=False,default='Pending')
    inspection_reviewed_by=Column(Integer,nullable=True)
    inspection_reviewed_at=Column(DateTime(timezone=True),nullable=True)
    created_by=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)
    # E2 master metadata: identity remains in this existing table.
    make=Column(String(120),nullable=True)
    model=Column(String(120),nullable=True)
    serial_number=Column(String(160),nullable=True)
    owner_company=Column(String(200),nullable=True)
    ownership_type=Column(String(24),nullable=False,default='Owned')
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=True,index=True)
    location=Column(String(200),nullable=True)
    custodian_user_id=Column(Integer,nullable=True)
    operating_condition=Column(String(24),nullable=False,default='Unknown')
    capacity=Column(String(160),nullable=True)
    operating_specs=Column(JSON,nullable=True)
    mobilized_on=Column(Date,nullable=True)
    demobilized_on=Column(Date,nullable=True)
    hire_contract_ref=Column(String(160),nullable=True)
    maintenance_requirements=Column(Text,nullable=True)
    tracking_mode=Column(String(24),nullable=False,default='Individual')
    quantity=Column(Integer,nullable=False,default=1)


class PlanningEquipmentMasterChange(Base):
    """Append-only audit of equipment master metadata changes; not a custody movement ledger."""
    __tablename__='planning_equipment_master_changes'
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    asset_id=Column(Integer,ForeignKey('planning_equipment_assets.id'),nullable=False,index=True)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False)
    changed_by=Column(Integer,nullable=False)
    changed_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)
    action=Column(String(30),nullable=False)
    reason=Column(Text,nullable=False)
    before_state=Column(JSON,nullable=False)
    after_state=Column(JSON,nullable=False)


class PlanningEquipmentCustodyMovement(Base):
    """E3 append-only operational custody events; never a Stores stock ledger."""
    __tablename__ = 'planning_equipment_custody_movements'
    __table_args__ = (UniqueConstraint('organization_id','request_key',name='uq_equipment_custody_request'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey('planning_equipment_assets.id'), nullable=False, index=True)
    allocation_id = Column(Integer, ForeignKey('planning_resource_allocations.id'), nullable=True)
    parent_issue_id = Column(Integer, ForeignKey('planning_equipment_custody_movements.id'), nullable=True)
    action = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    custodian_user_id = Column(Integer, nullable=False)
    location = Column(String(200), nullable=False)
    reason = Column(Text, nullable=False)
    evidence_ref = Column(String(240), nullable=False)
    request_key = Column(String(100), nullable=False)
    recorded_by = Column(Integer, nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PlanningEquipmentMaintenanceOrder(Base):
    """One maintenance lifecycle per individual asset; no Stores or Finance ledger."""
    __tablename__ = 'planning_equipment_maintenance_orders'
    __table_args__ = (UniqueConstraint('organization_id', 'request_key', name='uq_equipment_maintenance_request'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey('planning_equipment_assets.id'), nullable=False, index=True)
    request_key = Column(String(100), nullable=False)
    kind = Column(String(20), nullable=False)
    status = Column(String(24), nullable=False, default='Reported')
    title = Column(String(200), nullable=False)
    reported_reason = Column(Text, nullable=False)
    due_on = Column(Date, nullable=True)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    repair_completed_by = Column(Integer, nullable=True)
    repair_evidence_ref = Column(String(240), nullable=True)
    released_by = Column(Integer, nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)

class PlanningEquipmentMaintenanceEvent(Base):
    """Append-only E4 transition evidence and reviewer trace."""
    __tablename__ = 'planning_equipment_maintenance_events'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey('planning_equipment_maintenance_orders.id'), nullable=False, index=True)
    old_status = Column(String(24), nullable=True)
    new_status = Column(String(24), nullable=False)
    evidence_ref = Column(String(240), nullable=False)
    actor_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PlanningEquipmentInspectionDecision(Base):
    __tablename__='planning_equipment_inspection_decisions'
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    asset_id=Column(Integer,ForeignKey('planning_equipment_assets.id'),nullable=False,index=True)
    reviewer_id=Column(Integer,nullable=False)
    decision=Column(String(20),nullable=False)
    note=Column(Text,nullable=False)
    evidence_ref=Column(String(240),nullable=False)
    valid_through=Column(Date,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)


class PartnerPlanningCommitment(Base):
    """Company-scoped contractor response; never changes authoritative planning targets."""
    __tablename__ = 'planning_partner_commitments'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey('planning_schedules.id'), nullable=False)
    activity_id = Column(Integer, ForeignKey('planning_activities.id'), nullable=False)
    company_id = Column(Integer, nullable=False, index=True)
    submitted_by = Column(Integer, nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    commitment = Column(String(20), nullable=False)
    expected_date = Column(Date, nullable=True)
    note = Column(Text, nullable=False, default='')
    status = Column(String(20), nullable=False, default='Submitted')
    reviewed_by = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=False, default='')


class PlanningEquipmentComplianceEvidence(Base):
    """Evidence review for calibration, certification and inspection; not a statutory authority."""
    __tablename__ = 'planning_equipment_compliance_evidence'
    __table_args__ = (UniqueConstraint('organization_id','request_key',name='uq_equipment_compliance_request'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    asset_id=Column(Integer,ForeignKey('planning_equipment_assets.id'),nullable=False,index=True)
    request_key=Column(String(100),nullable=False)
    kind=Column(String(24),nullable=False)
    evidence_ref=Column(String(240),nullable=False)
    valid_through=Column(Date,nullable=False)
    required=Column(Boolean,nullable=False,default=True)
    status=Column(String(20),nullable=False,default='Pending')
    created_by=Column(Integer,nullable=False)
    reviewed_by=Column(Integer,nullable=True)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)
    reviewed_at=Column(DateTime(timezone=True),nullable=True)

class PlanningEquipmentSafetyHold(Base):
    """Independent HSE operational restriction, not an asset deletion or stock movement."""
    __tablename__ = 'planning_equipment_safety_holds'
    __table_args__ = (UniqueConstraint('organization_id','request_key',name='uq_equipment_safety_hold_request'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    asset_id=Column(Integer,ForeignKey('planning_equipment_assets.id'),nullable=False,index=True)
    request_key=Column(String(100),nullable=False)
    reason=Column(Text,nullable=False)
    evidence_ref=Column(String(240),nullable=False)
    status=Column(String(20),nullable=False,default='Active')
    created_by=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)
    released_by=Column(Integer,nullable=True)
    release_evidence_ref=Column(String(240),nullable=True)
    released_at=Column(DateTime(timezone=True),nullable=True)


class PlanningEquipmentUsageRecord(Base):
    """Append-only operating evidence; does not certify Construction or Finance progress."""
    __tablename__ = 'planning_equipment_usage_records'
    __table_args__ = (UniqueConstraint('organization_id','request_key',name='uq_equipment_usage_request_key'),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    project_id=Column(Integer,ForeignKey('projects.id'),nullable=False,index=True)
    asset_id=Column(Integer,ForeignKey('planning_equipment_assets.id'),nullable=False,index=True)
    allocation_id=Column(Integer,ForeignKey('planning_resource_allocations.id'),nullable=False)
    request_key=Column(String(100),nullable=False)
    starts_at=Column(DateTime(timezone=True),nullable=False)
    ends_at=Column(DateTime(timezone=True),nullable=False)
    operating_hours=Column(Numeric(12,3),nullable=False)
    idle_hours=Column(Numeric(12,3),nullable=False)
    breakdown_hours=Column(Numeric(12,3),nullable=False)
    maintenance_hours=Column(Numeric(12,3),nullable=False)
    meter_start=Column(Numeric(16,3),nullable=True)
    meter_end=Column(Numeric(16,3),nullable=True)
    fuel_liters=Column(Numeric(16,3),nullable=True)
    anomaly_note=Column(Text,nullable=True)
    evidence_ref=Column(String(240),nullable=False)
    recorded_by=Column(Integer,nullable=False)
    recorded_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)
