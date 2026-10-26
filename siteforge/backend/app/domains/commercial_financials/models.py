"""Phase 31.1: financial budget control. No synthetic costs or payments."""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import ForeignKey, String, Numeric, DateTime, Integer, UniqueConstraint, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class FinanceCostCode(Base):
    __tablename__='finance_cost_codes'
    __table_args__=(UniqueConstraint('project_id','code'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    code:Mapped[str]=mapped_column(String(80))
    description:Mapped[str]=mapped_column(String(240))
    category:Mapped[str]=mapped_column(String(64))
    discipline_id:Mapped[int|None]=mapped_column(ForeignKey('disciplines.id'),nullable=True)

class FinanceBudget(Base):
    __tablename__='finance_budgets'
    __table_args__=(UniqueConstraint('project_id','code','revision'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    code:Mapped[str]=mapped_column(String(80))
    revision:Mapped[int]=mapped_column(Integer,default=1)
    cost_code_id:Mapped[int]=mapped_column(ForeignKey('finance_cost_codes.id'))
    description:Mapped[str]=mapped_column(String(240))
    currency:Mapped[str]=mapped_column(String(3))
    proposed_amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    forecast_remaining:Mapped[Decimal|None]=mapped_column(Numeric(20,2),nullable=True)
    status:Mapped[str]=mapped_column(String(30),default='Draft')
    submitted_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    approved_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    approved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    decision_reason:Mapped[str]=mapped_column(Text,default='')


class FinanceProcurementAllocation(Base):
    """Finance-owned cost coding for a Procurement-owned purchase order."""
    __tablename__ = 'finance_procurement_allocations'
    __table_args__ = (UniqueConstraint('project_id', 'purchase_order_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    purchase_order_id:Mapped[int]=mapped_column(ForeignKey('purchase_orders.id'),index=True)
    cost_code_id:Mapped[int]=mapped_column(ForeignKey('finance_cost_codes.id'))
    assigned_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    assigned_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))


class FinanceSupplierInvoicePosting(Base):
    """One finance verification per Procurement invoice; no duplicate invoice header."""
    __tablename__ = 'finance_supplier_invoice_postings'
    __table_args__ = (UniqueConstraint('project_id', 'vendor_invoice_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    vendor_invoice_id:Mapped[int]=mapped_column(ForeignKey('vendor_invoices.id'),index=True)
    purchase_order_id:Mapped[int]=mapped_column(ForeignKey('purchase_orders.id'))
    cost_code_id:Mapped[int]=mapped_column(ForeignKey('finance_cost_codes.id'))
    currency:Mapped[str]=mapped_column(String(8))
    amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    posted_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    posted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    verification_note:Mapped[str]=mapped_column(Text,default='')


class FinanceContract(Base):
    """Finance contract register; purchase orders remain Procurement-owned."""
    __tablename__ = 'finance_contracts'
    __table_args__ = (UniqueConstraint('project_id', 'number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    number:Mapped[str]=mapped_column(String(80))
    contract_type:Mapped[str]=mapped_column(String(40))
    counterparty_company_id:Mapped[int]=mapped_column(ForeignKey('companies.id'))
    currency:Mapped[str]=mapped_column(String(3))
    original_value:Mapped[Decimal]=mapped_column(Numeric(20,2))
    status:Mapped[str]=mapped_column(String(30),default='Draft')
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class FinanceBoqLine(Base):
    __tablename__='finance_boq_lines'
    __table_args__=(UniqueConstraint('contract_id','code'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('finance_contracts.id'),index=True)
    code:Mapped[str]=mapped_column(String(80))
    description:Mapped[str]=mapped_column(String(240))
    activity_id:Mapped[int]=mapped_column(ForeignKey('construction_activities.id'))
    unit:Mapped[str]=mapped_column(String(40))
    quantity:Mapped[Decimal]=mapped_column(Numeric(18,3))
    unit_rate:Mapped[Decimal]=mapped_column(Numeric(20,2))
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))

class FinanceMeasurement(Base):
    """Immutable certified-quantity snapshot; draft rows do not recognize cost."""
    __tablename__='finance_measurements'
    __table_args__=(UniqueConstraint('project_id','number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('finance_contracts.id'))
    boq_line_id:Mapped[int]=mapped_column(ForeignKey('finance_boq_lines.id'))
    number:Mapped[str]=mapped_column(String(80))
    claimed_quantity:Mapped[Decimal]=mapped_column(Numeric(18,3))
    certified_quantity:Mapped[Decimal]=mapped_column(Numeric(18,3),default=0)
    unit_rate_snapshot:Mapped[Decimal]=mapped_column(Numeric(20,2))
    status:Mapped[str]=mapped_column(String(30),default='Draft')
    evidence_note:Mapped[str]=mapped_column(Text,default='')
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    certified_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    certified_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class FinanceSubcontractBill(Base):
    __tablename__='finance_subcontract_bills'
    __table_args__=(UniqueConstraint('project_id','number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('finance_contracts.id'))
    measurement_id:Mapped[int]=mapped_column(ForeignKey('finance_measurements.id'),unique=True)
    number:Mapped[str]=mapped_column(String(80))
    gross_value:Mapped[Decimal]=mapped_column(Numeric(20,2))
    retention_amount:Mapped[Decimal]=mapped_column(Numeric(20,2),default=0)
    advance_recovery_amount:Mapped[Decimal]=mapped_column(Numeric(20,2),default=0)
    other_deduction_amount:Mapped[Decimal]=mapped_column(Numeric(20,2),default=0)
    net_payable:Mapped[Decimal]=mapped_column(Numeric(20,2),default=0)
    posted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    posted_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    status:Mapped[str]=mapped_column(String(30),default='Draft')
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))


class FinanceBillLine(Base):
    """One certified measurement may appear on exactly one RA bill."""
    __tablename__ = 'finance_bill_lines'
    __table_args__ = (UniqueConstraint('measurement_id'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    bill_id:Mapped[int] = mapped_column(ForeignKey('finance_subcontract_bills.id'),index=True)
    measurement_id:Mapped[int] = mapped_column(ForeignKey('finance_measurements.id'))
    value_snapshot:Mapped[Decimal] = mapped_column(Numeric(20,2))

class FinanceBillDecision(Base):
    __tablename__ = 'finance_bill_decisions'
    id:Mapped[int] = mapped_column(primary_key=True)
    bill_id:Mapped[int] = mapped_column(ForeignKey('finance_subcontract_bills.id'),index=True)
    actor_id:Mapped[int] = mapped_column(ForeignKey('users.id'))
    action:Mapped[str] = mapped_column(String(40))
    reason:Mapped[str] = mapped_column(Text)
    occurred_at:Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))


class FinanceClientClaim(Base):
    """Client revenue is distinct from project cost and draft claims from receivables."""
    __tablename__='finance_client_claims'
    __table_args__=(UniqueConstraint('project_id','number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('finance_contracts.id'),index=True)
    number:Mapped[str]=mapped_column(String(80))
    billing_period:Mapped[str]=mapped_column(String(40))
    amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    certified_value:Mapped[Decimal]=mapped_column(Numeric(20,2),default=0)
    currency:Mapped[str]=mapped_column(String(3))
    status:Mapped[str]=mapped_column(String(36),default='Draft')
    evidence_reference:Mapped[str]=mapped_column(Text)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    certified_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    certified_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    due_date:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class FinanceClientClaimLine(Base):
    __tablename__='finance_client_claim_lines'
    __table_args__=(UniqueConstraint('measurement_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    claim_id:Mapped[int]=mapped_column(ForeignKey('finance_client_claims.id'),index=True)
    measurement_id:Mapped[int]=mapped_column(ForeignKey('finance_measurements.id'))
    value_snapshot:Mapped[Decimal]=mapped_column(Numeric(20,2))

class FinanceClientCollection(Base):
    __tablename__='finance_client_collections'
    __table_args__=(UniqueConstraint('project_id','transaction_reference'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    claim_id:Mapped[int]=mapped_column(ForeignKey('finance_client_claims.id'),index=True)
    amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    currency:Mapped[str]=mapped_column(String(3))
    received_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    transaction_reference:Mapped[str]=mapped_column(String(120))
    evidence_reference:Mapped[str]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class FinanceClientClaimDecision(Base):
    __tablename__='finance_client_claim_decisions'
    id:Mapped[int]=mapped_column(primary_key=True)
    claim_id:Mapped[int]=mapped_column(ForeignKey('finance_client_claims.id'),index=True)
    actor_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    action:Mapped[str]=mapped_column(String(40))
    note:Mapped[str]=mapped_column(Text)
    occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))


class FinanceDirectExpense(Base):
    __tablename__='finance_direct_expenses'
    __table_args__=(UniqueConstraint('project_id','number'),UniqueConstraint('project_id','source_reference'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    number:Mapped[str]=mapped_column(String(80))
    cost_code_id:Mapped[int]=mapped_column(ForeignKey('finance_cost_codes.id'))
    source_reference:Mapped[str]=mapped_column(String(160))
    description:Mapped[str]=mapped_column(Text)
    currency:Mapped[str]=mapped_column(String(3))
    amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    status:Mapped[str]=mapped_column(String(32),default='Draft')
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    approved_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    approved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    evidence_reference:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class FinanceVariation(Base):
    __tablename__='finance_variations'
    __table_args__=(UniqueConstraint('project_id','number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('finance_contracts.id'))
    number:Mapped[str]=mapped_column(String(80))
    description:Mapped[str]=mapped_column(Text)
    cost_impact:Mapped[Decimal]=mapped_column(Numeric(20,2))
    revenue_impact:Mapped[Decimal]=mapped_column(Numeric(20,2))
    currency:Mapped[str]=mapped_column(String(3))
    status:Mapped[str]=mapped_column(String(32),default='Draft')
    evidence_reference:Mapped[str]=mapped_column(Text)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    approved_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    approved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class FinanceBalanceEntry(Base):
    """Explicit advance/retention movements; no cost recognition or payment execution."""
    __tablename__='finance_balance_entries'
    __table_args__=(UniqueConstraint('project_id','reference'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    contract_id:Mapped[int]=mapped_column(ForeignKey('finance_contracts.id'))
    reference:Mapped[str]=mapped_column(String(120))
    balance_type:Mapped[str]=mapped_column(String(32))
    movement:Mapped[str]=mapped_column(String(16))
    currency:Mapped[str]=mapped_column(String(3))
    amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    evidence_reference:Mapped[str]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    recorded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))


class FinancePaymentRequest(Base):
    """Approval of payable settlement; does not execute a bank transfer."""
    __tablename__='finance_payment_requests'
    __table_args__=(UniqueConstraint('project_id','number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    bill_id:Mapped[int]=mapped_column(ForeignKey('finance_subcontract_bills.id'),index=True)
    number:Mapped[str]=mapped_column(String(80))
    amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    currency:Mapped[str]=mapped_column(String(3))
    due_date:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    status:Mapped[str]=mapped_column(String(32),default='Draft')
    evidence_reference:Mapped[str]=mapped_column(Text)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    approved_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    approved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class FinancePaymentRecord(Base):
    """Evidence of an externally executed payment allocated to one approved request."""
    __tablename__='finance_payment_records'
    __table_args__=(UniqueConstraint('project_id','transaction_reference'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    payment_request_id:Mapped[int]=mapped_column(ForeignKey('finance_payment_requests.id'),index=True)
    amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    currency:Mapped[str]=mapped_column(String(3))
    paid_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    transaction_reference:Mapped[str]=mapped_column(String(160))
    evidence_reference:Mapped[str]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))


class FinanceSupplierPaymentRequest(Base):
    """Finance settlement instruction for an already posted Procurement-owned invoice."""
    __tablename__='finance_supplier_payment_requests'
    __table_args__=(UniqueConstraint('project_id','number'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    invoice_posting_id:Mapped[int]=mapped_column(ForeignKey('finance_supplier_invoice_postings.id'),index=True)
    number:Mapped[str]=mapped_column(String(80))
    amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    currency:Mapped[str]=mapped_column(String(8))
    due_date:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    status:Mapped[str]=mapped_column(String(32),default='Draft')
    evidence_reference:Mapped[str]=mapped_column(Text)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    approved_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    approved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class FinanceSupplierPaymentRecord(Base):
    """Record external payment evidence, never initiate transfers."""
    __tablename__='finance_supplier_payment_records'
    __table_args__=(UniqueConstraint('project_id','transaction_reference'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    request_id:Mapped[int]=mapped_column(ForeignKey('finance_supplier_payment_requests.id'),index=True)
    amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    currency:Mapped[str]=mapped_column(String(8))
    paid_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    transaction_reference:Mapped[str]=mapped_column(String(160))
    evidence_reference:Mapped[str]=mapped_column(Text)
    recorded_by:Mapped[int]=mapped_column(ForeignKey('users.id'))


class FinancePaymentApprovalLimit(Base):
    """Project-specific maximum payment request value for an authorized approver."""
    __tablename__ = 'finance_payment_approval_limits'
    __table_args__ = (UniqueConstraint('project_id', 'user_id', 'currency', 'payment_type'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    project_id:Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    user_id:Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    currency:Mapped[str] = mapped_column(String(3))
    payment_type:Mapped[str] = mapped_column(String(24))
    maximum_amount:Mapped[Decimal] = mapped_column(Numeric(20,2))
    active:Mapped[bool] = mapped_column(default=True)
    configured_by:Mapped[int] = mapped_column(ForeignKey('users.id'))
    configured_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))


class FinanceAuthorityAudit(Base):
    """Append-only evidence for monetary approval authority changes."""
    __tablename__='finance_authority_audit'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    authority_id:Mapped[int]=mapped_column(ForeignKey('finance_payment_approval_limits.id'),index=True)
    target_user_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    changed_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    currency:Mapped[str]=mapped_column(String(3))
    payment_type:Mapped[str]=mapped_column(String(24))
    previous_amount:Mapped[Decimal|None]=mapped_column(Numeric(20,2),nullable=True)
    new_amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    previous_active:Mapped[bool|None]=mapped_column(nullable=True)
    new_active:Mapped[bool]=mapped_column()
    reason:Mapped[str]=mapped_column(Text)
    changed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class FinancePaymentDecisionAudit(Base):
    """Append-only evidence for supplier/subcontract payment authorization."""
    __tablename__='finance_payment_decision_audit'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    payment_type:Mapped[str]=mapped_column(String(24))
    request_id:Mapped[int]=mapped_column(Integer)
    decision:Mapped[str]=mapped_column(String(24))
    actor_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    request_amount:Mapped[Decimal]=mapped_column(Numeric(20,2))
    currency:Mapped[str]=mapped_column(String(3))
    authority_mode:Mapped[str]=mapped_column(String(40))
    reason:Mapped[str]=mapped_column(Text)
    decided_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))


class FinanceSettlementReversal(Base):
    """Immutable compensating evidence; original external payment is never deleted."""
    __tablename__ = 'finance_settlement_reversals'
    __table_args__ = (UniqueConstraint('project_id', 'payment_type', 'payment_record_id'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    project_id:Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    payment_type:Mapped[str] = mapped_column(String(24))
    payment_record_id:Mapped[int] = mapped_column(Integer)
    original_amount:Mapped[Decimal] = mapped_column(Numeric(20,2))
    currency:Mapped[str] = mapped_column(String(3))
    reason:Mapped[str] = mapped_column(Text)
    evidence_reference:Mapped[str] = mapped_column(Text)
    reversed_by:Mapped[int] = mapped_column(ForeignKey('users.id'))
    reversed_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))


class FinancePeriod(Base):
    """Project/currency monthly close with explicit reopen audit."""
    __tablename__ = 'finance_periods'
    __table_args__ = (UniqueConstraint('project_id', 'currency', 'period_start'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    project_id:Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    currency:Mapped[str] = mapped_column(String(3))
    period_start:Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status:Mapped[str] = mapped_column(String(16), default='Open')
    closed_by:Mapped[int|None] = mapped_column(ForeignKey('users.id'), nullable=True)
    closed_at:Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)

class FinancePeriodDecision(Base):
    __tablename__ = 'finance_period_decisions'
    id:Mapped[int] = mapped_column(primary_key=True)
    period_id:Mapped[int] = mapped_column(ForeignKey('finance_periods.id'), index=True)
    project_id:Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    action:Mapped[str] = mapped_column(String(16))
    reason:Mapped[str] = mapped_column(Text)
    actor_id:Mapped[int] = mapped_column(ForeignKey('users.id'))
    recorded_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))


class FinanceApprovalPolicy(Base):
    """Optional strict approval authority and escalation policy per project/payment type."""
    __tablename__ = 'finance_approval_policies'
    __table_args__ = (UniqueConstraint('project_id', 'payment_type', name='uq_finance_approval_policy'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    project_id:Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    payment_type:Mapped[str] = mapped_column(String(24))
    require_configured_authority:Mapped[bool] = mapped_column(default=False)
    overdue_after_hours:Mapped[int] = mapped_column(default=48)
    changed_by:Mapped[int] = mapped_column(ForeignKey('users.id'))
    changed_at:Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))


class FinanceApprovalPolicyAudit(Base):
    """Append-only history of project payment approval control changes."""
    __tablename__='finance_approval_policy_audit'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    payment_type:Mapped[str]=mapped_column(String(24))
    actor_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    previous_policy:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    new_policy:Mapped[dict]=mapped_column(JSON)
    reason:Mapped[str]=mapped_column(Text)
    changed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class FinanceInventoryCostingPolicy(Base):
    """Finance authority for inventory costing; does not post stock or journals."""
    __tablename__ = 'finance_inventory_costing_policies'
    __table_args__ = (UniqueConstraint('project_id', 'revision'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    organization_id:Mapped[int] = mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int] = mapped_column(ForeignKey('projects.id'),index=True)
    revision:Mapped[int] = mapped_column(Integer)
    costing_method:Mapped[str] = mapped_column(String(32))
    currency:Mapped[str] = mapped_column(String(3))
    effective_note:Mapped[str] = mapped_column(Text)
    status:Mapped[str] = mapped_column(String(24),default='Draft')
    created_by:Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    submitted_by:Mapped[int|None] = mapped_column(ForeignKey('users.id'),nullable=True)
    approved_by:Mapped[int|None] = mapped_column(ForeignKey('users.id'),nullable=True)
    approved_at:Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)
    decision_reason:Mapped[str] = mapped_column(Text,default='')


class FinanceLandedCostBatch(Base):
    """Finance-owned receipt cost evidence; NOT an inventory valuation or journal."""
    __tablename__ = 'finance_landed_cost_batches'
    __table_args__ = (UniqueConstraint('project_id','document_ref'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    organization_id:Mapped[int] = mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int] = mapped_column(ForeignKey('projects.id'),index=True)
    document_ref:Mapped[str] = mapped_column(String(100))
    category:Mapped[str] = mapped_column(String(40))
    currency:Mapped[str] = mapped_column(String(3))
    amount:Mapped[Decimal] = mapped_column(Numeric(20,2))
    source_document:Mapped[str] = mapped_column(String(200))
    status:Mapped[str] = mapped_column(String(24),default='Draft')
    created_by:Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    submitted_by:Mapped[int|None] = mapped_column(ForeignKey('users.id'),nullable=True)
    approved_by:Mapped[int|None] = mapped_column(ForeignKey('users.id'),nullable=True)
    approved_at:Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)
    decision_reason:Mapped[str] = mapped_column(Text,default='')

class FinanceLandedCostReceiptLink(Base):
    """Scope of the charge, not a second goods-receipt or stock ledger."""
    __tablename__ = 'finance_landed_cost_receipt_links'
    __table_args__ = (UniqueConstraint('batch_id','goods_receipt_line_id'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    batch_id:Mapped[int] = mapped_column(ForeignKey('finance_landed_cost_batches.id'),index=True)
    goods_receipt_line_id:Mapped[int] = mapped_column(ForeignKey('goods_receipt_lines.id'),index=True)


class FinanceReceiptCostAllocation(Base):
    """Finance approval of invoice-line cost assigned to one GRN line; not a journal."""
    __tablename__ = 'finance_receipt_cost_allocations'
    __table_args__ = (UniqueConstraint('project_id','goods_receipt_line_id','vendor_invoice_line_id',name='uq_finance_receipt_invoice_allocation'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    organization_id:Mapped[int] = mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int] = mapped_column(ForeignKey('projects.id'),index=True)
    goods_receipt_line_id:Mapped[int] = mapped_column(ForeignKey('goods_receipt_lines.id'),index=True)
    vendor_invoice_line_id:Mapped[int] = mapped_column(ForeignKey('vendor_invoice_lines.id'),index=True)
    quantity:Mapped[Decimal] = mapped_column(Numeric(20,6))
    currency:Mapped[str] = mapped_column(String(3))
    unit_cost:Mapped[Decimal] = mapped_column(Numeric(20,6))
    source_reference:Mapped[str] = mapped_column(String(160))
    status:Mapped[str] = mapped_column(String(24),default='Draft')
    created_by:Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    submitted_by:Mapped[int|None] = mapped_column(ForeignKey('users.id'),nullable=True)
    approved_by:Mapped[int|None] = mapped_column(ForeignKey('users.id'),nullable=True)
    approved_at:Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)
    decision_reason:Mapped[str] = mapped_column(Text,default='')


class FinanceMovementJournalProposal(Base):
    """Finance-owned balanced proposal. Approval is NOT GL posting."""
    __tablename__ = 'finance_movement_journal_proposals'
    __table_args__ = (UniqueConstraint('project_id','source_movement_line_id','proposal_revision',name='uq_finance_movement_proposal_revision'),)
    id:Mapped[int] = mapped_column(primary_key=True)
    organization_id:Mapped[int] = mapped_column(ForeignKey('organizations.id'),index=True)
    project_id:Mapped[int] = mapped_column(ForeignKey('projects.id'),index=True)
    source_movement_line_id:Mapped[int] = mapped_column(ForeignKey('stock_posting_lines.id'),index=True)
    proposal_revision:Mapped[int] = mapped_column(Integer,default=1)
    currency:Mapped[str] = mapped_column(String(3))
    description:Mapped[str] = mapped_column(String(400))
    lines:Mapped[list] = mapped_column(JSON)
    status:Mapped[str] = mapped_column(String(24),default='Draft')
    created_by:Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    submitted_by:Mapped[int|None] = mapped_column(ForeignKey('users.id'),nullable=True)
    approved_by:Mapped[int|None] = mapped_column(ForeignKey('users.id'),nullable=True)
    approved_at:Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)
    decision_reason:Mapped[str] = mapped_column(Text,default='')
