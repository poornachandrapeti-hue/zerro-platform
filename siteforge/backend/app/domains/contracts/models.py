"""Contracts is authoritative for commercial terms; Finance retains historical postings."""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import ForeignKey, String, Integer, DateTime, Numeric, Text, JSON, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

def now(): return datetime.now(timezone.utc)

class Contract(Base):
    __tablename__='contract_register'
    __table_args__=(UniqueConstraint('organization_id','number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    number:Mapped[str]=mapped_column(String(80))
    title:Mapped[str]=mapped_column(String(240))
    contract_type:Mapped[str]=mapped_column(String(40))
    contracting_company_id:Mapped[int]=mapped_column(ForeignKey('companies.id'))
    counterparty_company_id:Mapped[int]=mapped_column(ForeignKey('companies.id'))
    manager_user_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    scope:Mapped[str]=mapped_column(Text)
    currency:Mapped[str|None]=mapped_column(String(3),nullable=True)
    original_value:Mapped[Decimal|None]=mapped_column(Numeric(20,2),nullable=True)
    effective_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    lifecycle:Mapped[str]=mapped_column(String(45),default='Draft')
    approval_state:Mapped[str]=mapped_column(String(40),default='Draft')
    current_version:Mapped[int]=mapped_column(Integer,default=1)
    published_version:Mapped[int|None]=mapped_column(Integer,nullable=True)
    execution_evidence:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ContractVersion(Base):
    __tablename__='contract_versions'
    __table_args__=(UniqueConstraint('contract_id','version'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    version:Mapped[int]=mapped_column(Integer)
    snapshot:Mapped[dict]=mapped_column(JSON)
    state:Mapped[str]=mapped_column(String(30),default='Draft')
    reason:Mapped[str]=mapped_column(Text)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ContractBoq(Base):
    __tablename__='contract_boq_version_lines'
    __table_args__=(UniqueConstraint('version_id','code'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    version_id:Mapped[int]=mapped_column(ForeignKey('contract_versions.id'),index=True)
    code:Mapped[str]=mapped_column(String(80))
    description:Mapped[str]=mapped_column(Text)
    unit:Mapped[str]=mapped_column(String(40))
    quantity:Mapped[Decimal]=mapped_column(Numeric(20,4))
    rate:Mapped[Decimal]=mapped_column(Numeric(20,2))
    currency:Mapped[str]=mapped_column(String(3))
    pricing_type:Mapped[str]=mapped_column(String(35),default='Quantity')

class ContractRecord(Base):
    """Source-linked typed subregister: obligations, notices, securities, claims, reviews, closeout."""
    __tablename__='contract_records'
    __table_args__=(UniqueConstraint('contract_id','category','number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    version_id:Mapped[int|None]=mapped_column(ForeignKey('contract_versions.id'),nullable=True)
    category:Mapped[str]=mapped_column(String(35),index=True)
    number:Mapped[str]=mapped_column(String(80))
    summary:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(40),default='Draft')
    due_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    amount:Mapped[Decimal|None]=mapped_column(Numeric(20,2),nullable=True)
    currency:Mapped[str|None]=mapped_column(String(3),nullable=True)
    evidence:Mapped[str|None]=mapped_column(Text,nullable=True)
    details:Mapped[dict]=mapped_column(JSON,default=dict)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ContractPartnerShare(Base):
    __tablename__='contract_partner_shares'
    __table_args__=(UniqueConstraint('contract_id','company_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    company_id:Mapped[int]=mapped_column(ForeignKey('companies.id'),index=True)
    published_version:Mapped[int]=mapped_column(Integer)
    can_submit:Mapped[bool]=mapped_column(Boolean,default=False)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    shared_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ContractAudit(Base):
    __tablename__='contract_audit_events'
    id:Mapped[int]=mapped_column(primary_key=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    actor_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    action:Mapped[str]=mapped_column(String(80))
    detail:Mapped[dict]=mapped_column(JSON,default=dict)
    at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ContractLegacyMap(Base):
    __tablename__='contract_financial_legacy_map'
    __table_args__=(UniqueConstraint('finance_contract_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    finance_contract_id:Mapped[int]=mapped_column(ForeignKey('finance_contracts.id'))
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'))
    version_id:Mapped[int]=mapped_column(ForeignKey('contract_versions.id'))
    mapped_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    mapped_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class ContractApprovalDecision(Base):
    """Immutable approval evidence tied to one exact contract version."""
    __tablename__ = 'contract_approval_decisions'
    __table_args__ = (UniqueConstraint('contract_id', 'version_id', 'decision'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey('contract_register.id'), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey('contract_versions.id'), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ContractReviewStage(Base):
    """Ordered approval assignments bound to one immutable version; never auto-approve."""
    __tablename__='contract_review_stages'
    __table_args__=(UniqueConstraint('version_id','step_no'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    version_id:Mapped[int]=mapped_column(ForeignKey('contract_versions.id'),index=True)
    step_no:Mapped[int]=mapped_column(Integer)
    label:Mapped[str]=mapped_column(String(120))
    reviewer_user_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    status:Mapped[str]=mapped_column(String(30),default='Waiting')
    decision_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    decided_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    decision_reason:Mapped[str|None]=mapped_column(Text,nullable=True)

class ContractSigningAuthority(Base):
    __tablename__='contract_signing_authorities'
    __table_args__=(UniqueConstraint('project_id','user_id','currency'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    currency:Mapped[str]=mapped_column(String(3))
    max_value:Mapped[Decimal]=mapped_column(Numeric(20,2))
    valid_from:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    valid_until:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ContractSigningDelegation(Base):
    __tablename__='contract_signing_delegations'
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    delegator_user_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    delegate_user_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    valid_from:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    valid_until:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class ContractAmendment(Base):
    """Formal signed variation amendment; previous versions remain immutable."""
    __tablename__='contract_amendments'
    __table_args__=(UniqueConstraint('variation_id'),UniqueConstraint('contract_id','amendment_number'))
    id:Mapped[int]=mapped_column(primary_key=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    variation_id:Mapped[int]=mapped_column(ForeignKey('contract_records.id'),index=True)
    amendment_number:Mapped[str]=mapped_column(String(80))
    delta_value:Mapped[Decimal]=mapped_column(Numeric(20,2))
    currency:Mapped[str]=mapped_column(String(3))
    status:Mapped[str]=mapped_column(String(35),default='Draft')
    prepared_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    approved_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    executed_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    approval_reason:Mapped[str|None]=mapped_column(Text,nullable=True)
    execution_evidence:Mapped[str|None]=mapped_column(Text,nullable=True)
    effective_version_id:Mapped[int|None]=mapped_column(ForeignKey('contract_versions.id'),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    effective_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class ContractModuleDelivery(Base):
    """Durable downstream handoff; module acknowledgment is separate from amendment execution."""
    __tablename__='contract_module_deliveries'
    __table_args__=(UniqueConstraint('amendment_id','destination'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    amendment_id:Mapped[int]=mapped_column(ForeignKey('contract_amendments.id'),index=True)
    destination:Mapped[str]=mapped_column(String(35))
    status:Mapped[str]=mapped_column(String(25),default='Pending')
    payload:Mapped[dict]=mapped_column(JSON)
    acknowledged_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    receipt_reference:Mapped[str|None]=mapped_column(String(160),nullable=True)
    acknowledged_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


class ContractConsumerProjection(Base):
    """Finance/Planning-owned received contract version; not a posting or baseline revision."""
    __tablename__ = 'contract_consumer_projections'
    __table_args__ = (UniqueConstraint('amendment_id', 'destination'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey('contract_register.id'), index=True)
    amendment_id: Mapped[int] = mapped_column(ForeignKey('contract_amendments.id'))
    destination: Mapped[str] = mapped_column(String(35))
    contract_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    received_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ContractFinanceLink(Base):
    """Explicit mapping; never alters legacy Finance bill or contract records."""
    __tablename__ = 'contract_finance_links'
    __table_args__ = (UniqueConstraint('contract_id'), UniqueConstraint('finance_contract_id'))
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey('contract_register.id'))
    finance_contract_id: Mapped[int] = mapped_column(ForeignKey('finance_contracts.id'))
    linked_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ContractScopeItem(Base):
    """Version-bound contractual scope and interface responsibility."""
    __tablename__ = 'contract_scope_items'
    __table_args__ = (UniqueConstraint('version_id', 'item_code'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey('contract_register.id'), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey('contract_versions.id'), index=True)
    item_code: Mapped[str] = mapped_column(String(80))
    item_type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    responsible_company_id: Mapped[int|None] = mapped_column(ForeignKey('companies.id'), nullable=True)
    responsible_user_id: Mapped[int|None] = mapped_column(ForeignKey('users.id'), nullable=True)
    reviewer_user_id: Mapped[int|None] = mapped_column(ForeignKey('users.id'), nullable=True)
    due_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    required_evidence: Mapped[str|None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ContractTermVersion(Base):
    """Structured commercial term attached to an exact contract version."""
    __tablename__ = 'contract_term_versions'
    __table_args__ = (UniqueConstraint('version_id', 'term_key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey('contract_register.id'), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey('contract_versions.id'), index=True)
    term_key: Mapped[str] = mapped_column(String(80))
    clause_reference: Mapped[str|None] = mapped_column(String(120), nullable=True)
    value: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ContractObligation(Base):
    """Trigger-based obligation: an unknown deadline remains NULL, never assumed overdue."""
    __tablename__='contract_obligations'
    __table_args__=(UniqueConstraint('contract_id','number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    version_id:Mapped[int]=mapped_column(ForeignKey('contract_versions.id'))
    number:Mapped[str]=mapped_column(String(80))
    clause_reference:Mapped[str|None]=mapped_column(String(120),nullable=True)
    description:Mapped[str]=mapped_column(Text)
    responsible_company_id:Mapped[int]=mapped_column(ForeignKey('companies.id'))
    owner_user_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    trigger_name:Mapped[str|None]=mapped_column(String(120),nullable=True)
    trigger_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    due_days:Mapped[int|None]=mapped_column(Integer,nullable=True)
    due_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    required_evidence:Mapped[str|None]=mapped_column(Text,nullable=True)
    acceptance_required:Mapped[bool]=mapped_column(Boolean,default=True)
    status:Mapped[str]=mapped_column(String(40),default='Not Started')
    evidence:Mapped[str|None]=mapped_column(Text,nullable=True)
    decision_evidence:Mapped[str|None]=mapped_column(Text,nullable=True)
    decided_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    decided_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class ContractClaim(Base):
    """Claim and EOT register; does not itself change effective contract value or Planning baselines."""
    __tablename__ = 'contract_claims'
    __table_args__ = (UniqueConstraint('contract_id','number'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    organization_id:Mapped[int] = mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int] = mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int] = mapped_column(ForeignKey('contract_register.id'),index=True)
    version_id:Mapped[int] = mapped_column(ForeignKey('contract_versions.id'))
    number:Mapped[str] = mapped_column(String(80))
    category:Mapped[str] = mapped_column(String(50))
    description:Mapped[str] = mapped_column(Text)
    event_at:Mapped[datetime] = mapped_column(DateTime(timezone=True))
    clause_reference:Mapped[str|None] = mapped_column(String(160),nullable=True)
    source_reference:Mapped[str|None] = mapped_column(Text,nullable=True)
    notice_required:Mapped[bool] = mapped_column(Boolean,default=False)
    notice_due_at:Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)
    notice_sent_at:Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)
    notice_evidence:Mapped[str|None] = mapped_column(Text,nullable=True)
    submission_due_at:Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)
    requested_amount:Mapped[Decimal|None] = mapped_column(Numeric(20,2),nullable=True)
    currency:Mapped[str|None] = mapped_column(String(3),nullable=True)
    requested_eot_days:Mapped[int|None] = mapped_column(Integer,nullable=True)
    calculation_evidence:Mapped[str|None] = mapped_column(Text,nullable=True)
    submission_evidence:Mapped[str|None] = mapped_column(Text,nullable=True)
    counterparty_response:Mapped[str|None] = mapped_column(Text,nullable=True)
    agreed_amount:Mapped[Decimal|None] = mapped_column(Numeric(20,2),nullable=True)
    agreed_eot_days:Mapped[int|None] = mapped_column(Integer,nullable=True)
    decision_evidence:Mapped[str|None] = mapped_column(Text,nullable=True)
    status:Mapped[str] = mapped_column(String(40),default='Draft')
    owner_user_id:Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_by:Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)


class ContractCorrespondence(Base):
    """Controlled contractual communication; draft != legally issued."""
    __tablename__='contract_correspondence_ledger'
    __table_args__=(UniqueConstraint('contract_id','number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    version_id:Mapped[int]=mapped_column(ForeignKey('contract_versions.id'))
    number:Mapped[str]=mapped_column(String(80))
    category:Mapped[str]=mapped_column(String(40))
    subject:Mapped[str]=mapped_column(String(240))
    content:Mapped[str]=mapped_column(Text)
    sender_company_id:Mapped[int]=mapped_column(ForeignKey('companies.id'))
    recipient_company_id:Mapped[int]=mapped_column(ForeignKey('companies.id'))
    linked_claim_id:Mapped[int|None]=mapped_column(ForeignKey('contract_claims.id'),nullable=True)
    response_due_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    status:Mapped[str]=mapped_column(String(32),default='Draft')
    approval_evidence:Mapped[str|None]=mapped_column(Text,nullable=True)
    approved_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    approved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    delivery_method:Mapped[str|None]=mapped_column(String(80),nullable=True)
    issue_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    dispatch_reference:Mapped[str|None]=mapped_column(String(240),nullable=True)
    dispatch_evidence:Mapped[str|None]=mapped_column(Text,nullable=True)
    receipt_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    receipt_evidence:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class ContractSecurityInstrument(Base):
    __tablename__='contract_security_instruments'
    __table_args__=(UniqueConstraint('contract_id','reference_number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    instrument_type:Mapped[str]=mapped_column(String(40))
    issuer:Mapped[str]=mapped_column(String(240))
    reference_number:Mapped[str]=mapped_column(String(120))
    amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    currency:Mapped[str]=mapped_column(String(3))
    issue_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    required_valid_until:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    renewal_owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    release_conditions:Mapped[str]=mapped_column(Text)
    evidence_ref:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(30),default='Active')
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ContractSecurityEvent(Base):
    __tablename__='contract_security_events'
    id:Mapped[int]=mapped_column(primary_key=True)
    instrument_id:Mapped[int]=mapped_column(ForeignKey('contract_security_instruments.id'),index=True)
    event_type:Mapped[str]=mapped_column(String(30))
    old_expiry:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    new_expiry:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    evidence_ref:Mapped[str]=mapped_column(Text)
    actor_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    recorded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class ContractCloseoutCheck(Base):
    __tablename__='contract_closeout_checks'
    __table_args__=(UniqueConstraint('contract_id','check_type'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    check_type:Mapped[str]=mapped_column(String(50))
    status:Mapped[str]=mapped_column(String(25),default='Pending')
    source_system:Mapped[str|None]=mapped_column(String(40),nullable=True)
    source_record_ref:Mapped[str|None]=mapped_column(Text,nullable=True)
    evidence_ref:Mapped[str|None]=mapped_column(Text,nullable=True)
    verified_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    verified_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class ContractWarranty(Base):
    __tablename__='contract_warranties'
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    description:Mapped[str]=mapped_column(Text)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    due_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    status:Mapped[str]=mapped_column(String(30),default='Open')
    evidence_ref:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class ContractPartnerDocument(Base):
    """Published document reference; bytes remain in the host's private document store."""
    __tablename__ = 'contract_partner_documents'
    __table_args__ = (UniqueConstraint('contract_id','company_id','document_key','revision'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('contract_register.id'),index=True)
    company_id:Mapped[int]=mapped_column(ForeignKey('companies.id'),index=True)
    contract_version_id:Mapped[int]=mapped_column(ForeignKey('contract_versions.id'))
    document_key:Mapped[str]=mapped_column(String(160))
    revision:Mapped[int]=mapped_column(Integer,default=1)
    display_name:Mapped[str]=mapped_column(String(240))
    document_class:Mapped[str]=mapped_column(String(50))
    private_storage_key:Mapped[str]=mapped_column(String(500))
    content_sha256:Mapped[str]=mapped_column(String(64))
    published_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    published_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


class ContractProcurementLink(Base):
    """Immutable governing agreement reference for an existing procurement PO."""
    __tablename__ = 'contract_procurement_links'
    __table_args__ = (UniqueConstraint('purchase_order_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey('contract_register.id'), index=True)
    contract_version_id: Mapped[int] = mapped_column(ForeignKey('contract_versions.id'))
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey('purchase_orders.id'))
    linked_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
