"""Phase 8 contract/free-issue reference readiness, not a financial or custody posting.

A contractor company match is NOT proof of a free-issue entitlement or title.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.contracts.models import Contract, ContractObligation
from app.domains.identity_projects.router import audit
from .material_handovers import _scope
from .models import StoresMaterialRequest, StoresMaterialHandover, StoresContractObligationLink

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Phase 8 Contract References'])


def contract_reference_readiness(requests, handovers, contracts, links=(), obligations=()):
    """Candidate matching only: never infer owner/title, entitlement or monetary recovery."""
    by_request = {}
    for handover in handovers:
        by_request.setdefault(handover.material_request_id, []).append(handover)
    link_by_request = {link.material_request_id: link for link in links}
    obligation_by_id = {ob.id: ob for ob in obligations}
    result = []
    for req in requests:
        candidates = [c for c in contracts if c.counterparty_company_id == req.requester_company_id]
        candidate_ids = sorted(c.id for c in candidates)
        related = by_request.get(req.id, [])
        link = link_by_request.get(req.id)
        ob = obligation_by_id.get(link.obligation_id) if link else None
        valid_link = bool(link and ob and ob.contract_id == link.contract_id
                          and any(c.id == link.contract_id for c in candidates))
        blockers = ['Ownership, permitted wastage and recovery terms are unverified']
        if not valid_link:
            blockers.append('No valid explicit contract obligation reference is linked to this Stores request')
        if not req.requirement_line_id:
            blockers.append('Canonical Procurement requirement line is missing')
        if not req.work_package_id:
            blockers.append('Construction work package is missing')
        if not req.requester_company_id:
            blockers.append('Requester company is missing')
        if not valid_link and len(candidate_ids) != 1:
            blockers.append('Contract candidate selection is ambiguous or missing')
        result.append({'material_request_id': req.id,
                       'requirement_line_id': req.requirement_line_id,
                       'requester_company_id': req.requester_company_id,
                       'work_package_id': req.work_package_id,
                       'planning_wbs_id': req.planning_wbs_id,
                       'material_item_id': req.item_id,
                       'unit': req.base_unit,
                       'request_status': req.status,
                       'handover_ids': sorted(h.id for h in related),
                       'contract_candidate_ids': candidate_ids,
                       'linked_contract_id': link.contract_id if valid_link else None,
                       'linked_obligation_id': link.obligation_id if valid_link else None,
                       'contract_reference_evidence_recorded': valid_link,
                       'explicit_contract_link_verified': valid_link,
                       'free_issue_entitlement_verified': False,
                       'finance_recovery_authorized': False,
                       'readiness': 'Blocked', 'blockers': blockers})
    return result


@router.get('/phase8/contract-free-issue-reference-readiness')
def contract_free_issue_reference_readiness(
    pid: int, work_package_id: int | None = None,
    u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    """Authorized internal reference-gap view; no contract prices or sensitive terms returned."""
    _scope(db, u, pid, 'stores.requests.review')
    if work_package_id is not None and work_package_id <= 0:
        raise HTTPException(422, 'Invalid work package ID')
    query = select(StoresMaterialRequest).where(
        StoresMaterialRequest.project_id == pid,
        StoresMaterialRequest.organization_id == u.organization_id)
    if work_package_id is not None:
        query = query.where(StoresMaterialRequest.work_package_id == work_package_id)
    requests = db.execute(query.order_by(StoresMaterialRequest.id.desc()).limit(500)).scalars().all()
    request_ids = [r.id for r in requests]
    handovers = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.project_id == pid,
        StoresMaterialHandover.material_request_id.in_(request_ids))).scalars().all() if request_ids else []
    company_ids = {r.requester_company_id for r in requests if r.requester_company_id is not None}
    contracts = db.execute(select(Contract).where(
        Contract.organization_id == u.organization_id,
        Contract.project_id == pid,
        Contract.counterparty_company_id.in_(company_ids))).scalars().all() if company_ids else []
    links = db.execute(select(StoresContractObligationLink).where(
        StoresContractObligationLink.organization_id == u.organization_id,
        StoresContractObligationLink.project_id == pid,
        StoresContractObligationLink.material_request_id.in_(request_ids))).scalars().all() if request_ids else []
    obligation_ids = [link.obligation_id for link in links]
    obligations = db.execute(select(ContractObligation).where(
        ContractObligation.organization_id == u.organization_id,
        ContractObligation.project_id == pid,
        ContractObligation.id.in_(obligation_ids))).scalars().all() if obligation_ids else []
    return {'records': contract_reference_readiness(requests, handovers, contracts, links, obligations),
            'as_of': datetime.now(timezone.utc),
            'coverage': 'Latest 500 project Stores requests; company matches are candidates only',
            'stock_verified': False, 'financial_values_exposed': False,
            'automatic_recovery_enabled': False}


class ContractObligationLinkIn(BaseModel):
    contract_id: int = Field(gt=0)
    obligation_id: int = Field(gt=0)
    evidence: str = Field(min_length=8, max_length=4000)


@router.post('/phase8/material-requests/{request_id}/contract-obligation-link')
def link_contract_obligation(pid: int, request_id: int, body: ContractObligationLinkIn,
                             u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Record a contract obligation reference; never interpret linkage as free-issue entitlement."""
    _scope(db, u, pid, 'stores.requests.review')
    req = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == request_id,
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid).with_for_update()).scalar_one_or_none()
    if req is None:
        raise HTTPException(404, 'Material request not found')
    if req.requester_company_id is None or req.requirement_line_id is None:
        raise HTTPException(409, 'Canonical requirement and contractor identity are required')
    contract = db.execute(select(Contract).where(
        Contract.id == body.contract_id, Contract.organization_id == u.organization_id,
        Contract.project_id == pid, Contract.counterparty_company_id == req.requester_company_id)).scalar_one_or_none()
    if contract is None:
        raise HTTPException(422, 'Contract is not scoped to this project and contractor')
    obligation = db.execute(select(ContractObligation).where(
        ContractObligation.id == body.obligation_id,
        ContractObligation.contract_id == contract.id,
        ContractObligation.organization_id == u.organization_id,
        ContractObligation.project_id == pid)).scalar_one_or_none()
    if obligation is None:
        raise HTTPException(422, 'Obligation does not belong to the selected contract')
    previous = db.execute(select(StoresContractObligationLink).where(
        StoresContractObligationLink.material_request_id == req.id).with_for_update()).scalar_one_or_none()
    if previous is not None:
        if (previous.contract_id == contract.id and previous.obligation_id == obligation.id
                and previous.evidence == body.evidence):
            return {'link_id': previous.id, 'status': 'Recorded', 'free_issue_entitlement_verified': False,
                    'finance_recovery_authorized': False, 'idempotent': True}
        raise HTTPException(409, 'An obligation is already linked; amendments require a separately audited workflow')
    entry = StoresContractObligationLink(organization_id=u.organization_id, project_id=pid,
        material_request_id=req.id, contract_id=contract.id, obligation_id=obligation.id,
        evidence=body.evidence, created_by=u.id)
    db.add(entry)
    db.flush()
    audit(db, u, 'link_stores_contract_obligation', 'stores_contract_obligation_links', entry.id, project_id=pid)
    db.commit()
    return {'link_id': entry.id, 'status': 'Recorded', 'free_issue_entitlement_verified': False,
            'finance_recovery_authorized': False, 'idempotent': False}
