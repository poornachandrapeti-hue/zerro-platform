"""E7A cross-domain equipment commercial handoff validation.

Only validates evidence/references. Procurement owns PO/contract authority, Stores owns
spares stock, Finance owns journal posting. No postings or duplicate ledgers here.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException


def _required(value, label):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 160:
        raise HTTPException(422, f'{label} reference is required (max 160 characters)')
    return value.strip()


def _nonnegative_money(value, label):
    try:
        number = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        raise HTTPException(422, f'Invalid {label}')
    if not number.is_finite() or number < 0 or number.as_tuple().exponent < -2:
        raise HTTPException(422, f'{label} must be nonnegative, finite and at most two decimal places')
    return number


def _scope(source, org_id, project_id, label):
    if source is None or getattr(source, 'organization_id', None) != org_id or getattr(source, 'project_id', None) != project_id:
        raise HTTPException(409, f'{label} must belong to the same organization and project')


def validate_hire_handoff(*, asset, contract, org_id, project_id, period_start,
                          period_end, rate, currency, evidence_ref, request_key):
    """Build an unposted costing *proposal* from an authoritative approved hire contract.

    The caller must load the contract from the Contracts domain, never from user-supplied
    fields. Rates, currency, and duration must be verified independently by Commercial.
    """
    _scope(asset, org_id, project_id, 'Equipment')
    _scope(contract, org_id, project_id, 'Hire contract')
    if getattr(asset, 'ownership_type', None) != 'Hired':
        raise HTTPException(409, 'Only hired assets can have hire-cost handoff')
    contract_ref = _required(getattr(contract, 'reference', None), 'Contract')
    if getattr(asset, 'hire_contract_ref', None) != contract_ref:
        raise HTTPException(409, 'Equipment hire contract reference does not match authoritative contract')
    if getattr(contract, 'status', None) != 'Approved':
        raise HTTPException(409, 'Approved hire contract required')
    if not isinstance(period_start, datetime) or not isinstance(period_end, datetime) or not period_start.tzinfo or not period_end.tzinfo:
        raise HTTPException(422, 'Timezone-aware hire period required')
    if period_start.astimezone(timezone.utc) >= period_end.astimezone(timezone.utc):
        raise HTTPException(422, 'Invalid hire period')
    approved_start = getattr(contract, 'starts_at', None)
    approved_end = getattr(contract, 'ends_at', None)
    if not approved_start or not approved_end or not approved_start.tzinfo or not approved_end.tzinfo:
        raise HTTPException(409, 'Authoritative contract period is missing')
    if period_start < approved_start or period_end > approved_end:
        raise HTTPException(409, 'Hire period outside approved contract')
    if not isinstance(currency, str) or currency.upper() != getattr(contract, 'currency', None):
        raise HTTPException(409, 'Hire currency mismatch')
    checked_rate = _nonnegative_money(rate, 'Hire rate')
    if checked_rate != _nonnegative_money(getattr(contract, 'approved_rate', None), 'Contract rate'):
        raise HTTPException(409, 'Hire rate differs from authoritative contract')
    return {'status': 'UnpostedProposal', 'posting_verified': False,
            'asset_id': asset.id, 'contract_ref': contract_ref,
            'project_id': project_id, 'organization_id': org_id,
            'period_start': period_start.isoformat(), 'period_end': period_end.isoformat(),
            'approved_rate': str(checked_rate), 'currency': currency.upper(),
            'evidence_ref': _required(evidence_ref, 'Hire evidence'),
            'request_key': _required(request_key, 'Idempotency key')}


def validate_spares_handoff(*, asset, stores_requirement, org_id, project_id,
                             quantity, request_key):
    """Validate a link to Stores-approved requirement; NEVER issue or deduct stock."""
    _scope(asset, org_id, project_id, 'Equipment')
    _scope(stores_requirement, org_id, project_id, 'Stores requirement')
    if getattr(stores_requirement, 'status', None) != 'Approved':
        raise HTTPException(409, 'Approved Stores requirement required')
    requirement_ref = _required(getattr(stores_requirement, 'reference', None), 'Stores requirement')
    try:
        qty = Decimal(str(quantity))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(422, 'Invalid spares quantity')
    if not qty.is_finite() or qty <= 0 or qty.as_tuple().exponent < -3:
        raise HTTPException(422, 'Spares quantity must be positive and at most 3 decimal places')
    authorized = getattr(stores_requirement, 'remaining_quantity', None)
    try:
        remaining = Decimal(str(authorized))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(409, 'Verified remaining Stores quantity required')
    if not remaining.is_finite() or qty > remaining:
        raise HTTPException(409, 'Spares quantity exceeds approved remaining requirement')
    return {'status': 'ReferenceValidated', 'stock_posted': False,
            'asset_id': asset.id, 'stores_requirement_ref': requirement_ref,
            'project_id': project_id, 'organization_id': org_id,
            'quantity': str(qty), 'request_key': _required(request_key, 'Idempotency key')}
