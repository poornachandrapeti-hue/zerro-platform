"""E7B: read ONLY existing Contracts/Stores authorities; no stock or Finance writes.

Finance hire-rate approval is a separate authority and is NOT implied by contract approval.
Callers must be authenticated and RBAC-scoped before invoking these functions.
"""
from decimal import Decimal
from fastapi import HTTPException
from app.domains.contracts.models import Contract
from app.domains.stores_inventory.models import StoresMaterialRequest
from app.domains.supply_chain.models import MaterialRequirement, RequirementLine


def _identity(row, org_id, project_id, name):
    if row is None or row.organization_id != org_id or row.project_id != project_id:
        raise HTTPException(404, f"{name} not found for project")
    return row


def read_hire_contract_authority(db, *, contract_id: int, org_id: int, project_id: int):
    """Read contract identity, lifecycle and scope; deliberately does NOT infer unit hire rates."""
    row = _identity(db.get(Contract, contract_id), org_id, project_id, "Contract")
    if row.approval_state != "Approved" or row.published_version is None:
        raise HTTPException(409, "Published approved contract is required")
    if row.lifecycle in ("Cancelled", "Terminated", "Closed"):
        raise HTTPException(409, "Inactive contract cannot authorize new hire")
    if not row.currency:
        raise HTTPException(409, "Contract currency not configured")
    return {"source": "Contracts", "contract_id": row.id,
            "reference": row.number, "version": row.published_version,
            "currency": row.currency, "effective_at": row.effective_at,
            "expires_at": row.expires_at, "scope_verified": True,
            "hire_rate_verified": False, "finance_posted": False}


def read_spares_request_authority(db, *, request_id: int, org_id: int, project_id: int):
    """Resolve Stores request to authoritative Procurement requirement line and header."""
    row = _identity(db.get(StoresMaterialRequest, request_id), org_id, project_id, "Stores request")
    if row.status != "Approved" or row.requirement_line_id is None:
        raise HTTPException(409, "Approved Stores request linked to requirement line required")
    line = db.get(RequirementLine, row.requirement_line_id)
    header = db.get(MaterialRequirement, line.requirement_id) if line else None
    _identity(header, org_id, project_id, "Material requirement")
    if header.status != "Approved" or header.impact_state == "Review required":
        raise HTTPException(409, "Approved material requirement without drawing impact required")
    if line.item_id != row.item_id or line.unit != row.base_unit:
        raise HTTPException(409, "Stores item/unit differs from approved requirement")
    amount = Decimal(str(row.requested_quantity))
    if amount <= 0 or amount > Decimal(str(line.quantity)):
        raise HTTPException(409, "Stores request quantity invalid for requirement line")
    return {"source": "Stores", "stores_request_id": row.id,
            "request_key": row.request_key, "requirement_line_id": line.id,
            "requirement_id": header.id, "item_id": line.item_id,
            "approved_request_qty": str(amount), "unit": row.base_unit,
            "work_package_id": row.work_package_id,
            "stock_posted": False, "remaining_stock_authorized": False,
            "finance_posted": False}
