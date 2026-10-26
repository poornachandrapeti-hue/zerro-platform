"""Phase 8: read-only material evidence for Progress review; never awards earned progress."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.construction.models import ConstructionActivity, ProgressLine, ProgressReport
from .material_requests import _project
from .models import StoresConstructionMaterialUsage, StoresMaterialHandover, StoresMaterialRequest
from app.domains.supply_chain.models import StockPostingLine, StockPosting

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Phase 8 Progress Evidence'])


def material_progress_evidence_rows(usages, handovers, requests, issue_lines, postings, progress_lines, reports, activities):
    """Evidence join is exact on issued posting + construction work package.

    QA-verified material usage does not establish a Progress milestone or earned quantity.
    """
    handovers_by_id = {x.id: x for x in handovers}
    requests_by_id = {x.id: x for x in requests}
    issue_by_id = {x.id: x for x in issue_lines}
    posting_by_id = {x.id: x for x in postings}
    report_by_id = {x.id: x for x in reports if x.status == 'Approved'}
    activity_by_id = {x.id: x for x in activities}
    progress_by_key = defaultdict(list)
    for line in progress_lines:
        report = report_by_id.get(line.report_id)
        activity = activity_by_id.get(line.activity_id)
        if report and activity and line.stock_posting_id is not None:
            progress_by_key[(line.stock_posting_id, activity.package_id)].append((report, line))
    output = []
    for usage in usages:
        handover = handovers_by_id.get(usage.handover_id)
        request = requests_by_id.get(handover.material_request_id) if handover else None
        issue_line = issue_by_id.get(handover.stock_posting_line_id) if handover else None
        posting = posting_by_id.get(issue_line.posting_id) if issue_line else None
        if (not request or not issue_line or not posting or posting.kind != 'Issue'
            or posting.status != 'Posted' or request.work_package_id != usage.work_package_id
            or request.item_id != usage.item_id or issue_line.item_id != usage.item_id
            or request.base_unit != usage.unit or issue_line.unit != usage.unit):
            raise HTTPException(409, 'Material usage source lineage cannot be verified')
        amount = Decimal(str(usage.quantity))
        if not amount.is_finite() or amount <= 0:
            raise HTTPException(409, 'Invalid usage quantity')
        linked = progress_by_key.get((posting.id, usage.work_package_id), [])
        output.append({
            'usage_id': usage.id, 'usage_status': usage.status, 'usage_type': usage.usage_type,
            'qa_verified_material_quantity': str(amount) if usage.status == 'Verified' else None,
            'pending_qa_material_quantity': str(amount) if usage.status == 'Pending QA' else None,
            'material_unit': usage.unit, 'material_item_id': usage.item_id,
            'material_request_id': request.id, 'requirement_line_id': request.requirement_line_id,
            'work_package_id': usage.work_package_id, 'planning_wbs_id': request.planning_wbs_id,
            'handover_id': handover.id, 'stock_issue_posting_id': posting.id,
            'qa_verifier_id': usage.verified_by if usage.status == 'Verified' else None,
            'approved_progress_evidence': [
                {'progress_report_id': report.id, 'progress_line_id': line.id,
                 'activity_id': line.activity_id, 'activity_quantity': str(line.quantity) if line.quantity is not None else None,
                 'activity_unit': line.unit} for report, line in linked
            ],
            'progress_review_state': 'QA Verified Material Evidence' if usage.status == 'Verified' else 'Material Evidence Not QA Verified',
            'progress_earned': False, 'billing_certified': False, 'physical_stock_verified': False,
        })
    return output


@router.get('/phase8/progress-material-evidence')
def progress_material_evidence(pid: int, work_package_id: int | None = None, limit: int = 200,
    u: User = Depends(authenticated), db: Session = Depends(get_db)):
    _project(db, u, pid, action='construction.view')
    if not 1 <= limit <= 500 or (work_package_id is not None and work_package_id <= 0):
        raise HTTPException(422, 'Invalid work-package filter or limit')
    query = select(StoresConstructionMaterialUsage).where(
        StoresConstructionMaterialUsage.project_id == pid,
        StoresConstructionMaterialUsage.organization_id == u.organization_id)
    if work_package_id is not None:
        query = query.where(StoresConstructionMaterialUsage.work_package_id == work_package_id)
    usages = db.execute(query.order_by(StoresConstructionMaterialUsage.id.desc()).limit(limit)).scalars().all()
    if not usages:
        return {'records': [], 'as_of': datetime.now(timezone.utc), 'coverage': 'No material evidence in selected window',
                'progress_earned': False, 'billing_certified': False, 'physical_stock_verified': False}
    handovers = db.execute(select(StoresMaterialHandover).where(
        StoresMaterialHandover.id.in_({x.handover_id for x in usages}),
        StoresMaterialHandover.organization_id == u.organization_id,
        StoresMaterialHandover.project_id == pid)).scalars().all()
    requests = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id.in_({x.material_request_id for x in handovers}),
        StoresMaterialRequest.organization_id == u.organization_id,
        StoresMaterialRequest.project_id == pid)).scalars().all()
    issue_lines = db.execute(select(StockPostingLine).where(
        StockPostingLine.id.in_({x.stock_posting_line_id for x in handovers}))).scalars().all() if handovers else []
    postings = db.execute(select(StockPosting).where(
        StockPosting.id.in_({x.posting_id for x in issue_lines}),
        StockPosting.organization_id == u.organization_id, StockPosting.project_id == pid)).scalars().all() if issue_lines else []
    progress_lines = db.execute(select(ProgressLine).where(
        ProgressLine.stock_posting_id.in_({x.id for x in postings}))).scalars().all() if postings else []
    reports = db.execute(select(ProgressReport).where(
        ProgressReport.id.in_({x.report_id for x in progress_lines}),
        ProgressReport.organization_id == u.organization_id,
        ProgressReport.project_id == pid, ProgressReport.status == 'Approved')).scalars().all() if progress_lines else []
    activities = db.execute(select(ConstructionActivity).where(
        ConstructionActivity.id.in_({x.activity_id for x in progress_lines}),
        ConstructionActivity.organization_id == u.organization_id,
        ConstructionActivity.project_id == pid)).scalars().all() if progress_lines else []
    records = material_progress_evidence_rows(usages, handovers, requests, issue_lines, postings, progress_lines, reports, activities)
    return {'records': records, 'as_of': datetime.now(timezone.utc),
        'coverage': f'Latest {limit} usage records by ID; project-authorized Construction viewer',
        'progress_earned': False, 'billing_certified': False, 'physical_stock_verified': False,
        'note': 'QA-verified material usage is evidence for Progress review, not automatically earned progress or certified billing.'}
