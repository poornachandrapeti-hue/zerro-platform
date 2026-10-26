"""Read-only evidence from authoritative Engineering and Procurement sources.

These indicators are deliberately NOT earned progress: stage weights and eligible
milestones must be approved and tied to source evidence before EPCC roll-up.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User
from app.domains.engineering_documents.models import Drawing, DrawingRevision
from app.domains.supply_chain.models import PurchaseOrder, GoodsReceipt
from .router import progress_scope

router = APIRouter(prefix='/api/projects/{pid}/progress/evidence', tags=['Progress Source Evidence'])


def scoped(obj, scope):
    if scope['all']:
        return True
    return any(obj.company_id == company and (not disciplines or obj.discipline_id in disciplines)
               for company, disciplines in scope['pairs'])


def engineering_evidence(drawings, revisions):
    by_drawing = {}
    for rev in revisions:
        by_drawing.setdefault(rev.drawing_id, []).append(rev)
    details = []
    for d in drawings:
        revs = by_drawing.get(d.id, [])
        # Each drawing is counted once, regardless of the number of revisions.
        released = any(r.release_state == 'Released' and r.released_at is not None for r in revs)
        details.append({'drawing_id': d.id, 'number': d.number,
                        'company_id': d.company_id, 'discipline_id': d.discipline_id,
                        'record_status': d.record_status, 'preparation': d.preparation,
                        'released_for_construction': released,
                        'revision_count': len(revs)})
    active = [x for x in details if x['record_status'] == 'Active']
    return {'active_drawings': len(active),
            'released_drawings': sum(x['released_for_construction'] for x in active),
            'drawings': details, 'earned_percent': None,
            'measure': 'Readiness count; not approved weighted earned progress'}


def procurement_evidence(orders, receipts):
    order_ids = {o.id for o in orders}
    rows = [{'order_id': o.id, 'number': o.number, 'status': o.status,
             'company_id': o.company_id, 'discipline_id': o.discipline_id,
             'receipt_count': 0} for o in orders]
    counts = {}
    for receipt in receipts:
        if receipt.purchase_order_id in order_ids and receipt.status == 'Posted':
            counts[receipt.purchase_order_id] = counts.get(receipt.purchase_order_id, 0) + 1
    for row in rows:
        row['receipt_count'] = counts.get(row['order_id'], 0)
    return {'orders': rows, 'purchase_order_count': len(rows),
            'orders_with_posted_receipts': sum(bool(row['receipt_count']) for row in rows),
            'earned_percent': None,
            'measure': 'Order and receipt counts; not approved weighted earned progress',
            'warning': 'Posted goods receipts do not establish inspection acceptance or package readiness'}


@router.get('/engineering')
def engineering(pid: int, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    scope = progress_scope(db, user, pid)
    drawings = [d for d in db.query(Drawing).filter_by(organization_id=user.organization_id, project_id=pid).all()
                if scoped(d, scope)]
    identifiers = [d.id for d in drawings]
    revisions = (db.query(DrawingRevision).filter(DrawingRevision.drawing_id.in_(identifiers)).all()
                 if identifiers else [])
    return engineering_evidence(drawings, revisions)


@router.get('/procurement')
def procurement(pid: int, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    scope = progress_scope(db, user, pid)
    orders = [o for o in db.query(PurchaseOrder).filter_by(organization_id=user.organization_id, project_id=pid).all()
              if scoped(o, scope)]
    identifiers = [o.id for o in orders]
    receipts = (db.query(GoodsReceipt).filter_by(organization_id=user.organization_id, project_id=pid)
                .filter(GoodsReceipt.purchase_order_id.in_(identifiers)).all() if identifiers else [])
    return procurement_evidence(orders, receipts)
