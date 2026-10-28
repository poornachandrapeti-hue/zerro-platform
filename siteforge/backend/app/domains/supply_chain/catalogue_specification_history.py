"""Append-only item-history snapshots; never mutate previously stored snapshots."""
from copy import deepcopy
from sqlalchemy import func
from .models import CatalogueItemSpecificationHistory


def item_snapshot(item):
    """Copy authoritative item metadata, excluding mutable identity/audit relationships."""
    return deepcopy({
        "code": item.code,
        "description": item.description,
        "item_type": item.item_type,
        "category": item.category,
        "discipline_ids": item.discipline_ids or [],
        "specification": item.specification,
        "specification_attributes": item.specification_attributes or {},
        "size_rating": item.size_rating,
        "base_unit": item.base_unit,
        "approved_make": item.approved_make,
        "inspection_required": item.inspection_required,
        "tracking_required": item.tracking_required,
        "active": item.active,
        "approval_status": item.approval_status,
    })


def record_item_history(db, user, item, event, reason=""):
    """Record a history event inside the caller's existing transaction.

    Lock the parent item before choosing the sequence so concurrent writers on
    PostgreSQL serialize; the unique DB constraint provides a final safeguard.
    """
    db.query(type(item)).filter(type(item).id == item.id).with_for_update().one()
    last = db.query(func.max(CatalogueItemSpecificationHistory.sequence)).filter(
        CatalogueItemSpecificationHistory.item_id == item.id
    ).scalar()
    row = CatalogueItemSpecificationHistory(
        organization_id=item.organization_id,
        item_id=item.id,
        sequence=(last or 0) + 1,
        item_version=item.version,
        event=event,
        reason=reason,
        snapshot=item_snapshot(item),
        actor_id=user.id,
    )
    db.add(row)
    db.flush()
    return row


def history_payload(row):
    return {
        "sequence": row.sequence, "item_version": row.item_version,
        "event": row.event, "reason": row.reason,
        "snapshot": deepcopy(row.snapshot), "actor_id": row.actor_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
