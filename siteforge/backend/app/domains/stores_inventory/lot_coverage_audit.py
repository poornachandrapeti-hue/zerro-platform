"""Read-only audit of legacy posting-line lot coverage; never determines releasable stock."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.supply_chain.models import StockPosting, StockPostingLine
from .models import StoresPostingLotAllocation, StoresOutboundLotAllocation
from .router import receipt_access

router = APIRouter(prefix="/api/projects/{pid}/stores", tags=["Stores & Inventory"])


def coverage(posted, attributed, kind):
    """Check one posted line without rounding, cross-item summing, or release side effects."""
    p, a = Decimal(str(posted)), Decimal(str(attributed))
    flags = []
    if p <= 0:
        flags.append("INVALID_POSTED_QUANTITY")
    if a < 0:
        flags.append("NEGATIVE_ATTRIBUTION")
    if a < p:
        flags.append("UNATTRIBUTED_QUANTITY")
    if a > p:
        flags.append("OVER_ATTRIBUTED_QUANTITY")
    return {"posting_kind": kind, "posted_quantity": str(p),
            "attributed_quantity": str(a), "unattributed_quantity": str(max(p-a, Decimal(0))),
            "flags": flags, "fully_attributed": not flags, "issue_authorized": False}


@router.get("/lot-posting-coverage")
def lot_posting_coverage(pid: int, warehouse_id: int | None = None,
                         limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                         u: User = Depends(authenticated), db: Session = Depends(get_db)):
    receipt_access(db, u, pid)
    q = (db.query(StockPostingLine, StockPosting)
         .join(StockPosting, StockPosting.id == StockPostingLine.posting_id)
         .filter(StockPosting.organization_id == u.organization_id,
                 StockPosting.project_id == pid, StockPosting.status == "Posted",
                 StockPosting.kind.in_(["Accept", "Issue", "Return"])))
    if warehouse_id is not None:
        q = q.filter(StockPosting.warehouse_id == warehouse_id)
    total = q.count()
    rows = q.order_by(StockPostingLine.id).offset(offset).limit(limit).all()
    line_ids = [line.id for line, _ in rows]
    accept = {}
    outbound = {}
    if line_ids:
        accept = dict(db.query(StoresPostingLotAllocation.stock_posting_line_id,
                               func.sum(StoresPostingLotAllocation.quantity))
                      .filter(StoresPostingLotAllocation.organization_id == u.organization_id,
                              StoresPostingLotAllocation.project_id == pid,
                              StoresPostingLotAllocation.stock_posting_line_id.in_(line_ids))
                      .group_by(StoresPostingLotAllocation.stock_posting_line_id).all())
        outbound = dict(db.query(StoresOutboundLotAllocation.stock_posting_line_id,
                                 func.sum(StoresOutboundLotAllocation.quantity))
                        .filter(StoresOutboundLotAllocation.organization_id == u.organization_id,
                                StoresOutboundLotAllocation.project_id == pid,
                                StoresOutboundLotAllocation.stock_posting_line_id.in_(line_ids))
                        .group_by(StoresOutboundLotAllocation.stock_posting_line_id).all())
    records = []
    for line, posting in rows:
        attributed = (accept if posting.kind == "Accept" else outbound).get(line.id, 0)
        records.append({"posting_id": posting.id, "posting_line_id": line.id,
                        "warehouse_id": posting.warehouse_id, "item_id": line.item_id,
                        "unit": line.unit, **coverage(line.quantity, attributed, posting.kind)})
    return {"project_id": pid, "warehouse_id": warehouse_id, "total_lines": total,
            "offset": offset, "limit": limit, "records": records,
            "fully_attributed_in_page": sum(1 for record in records if record["fully_attributed"]),
            "unattributed_in_page": sum(1 for record in records if not record["fully_attributed"]),
            "stock_release_enabled": False,
            "warning": "Page-level historical posting coverage only. No physical/available lot balances or stock release are authorized."}
