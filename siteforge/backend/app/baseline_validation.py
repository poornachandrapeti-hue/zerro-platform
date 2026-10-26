"""Validate milestone documents before SiteForge records or approves them."""
from datetime import date
from decimal import Decimal

def validate_document(doc, require_approved=True):
    if require_approved:
        if doc.get("approval_status") != "approved" or not all(doc.get(x) for x in ("approved_by","approved_on","approval_reference","revision")):
            raise ValueError("Approved provenance required")
        date.fromisoformat(doc["approved_on"])
    records=doc.get("activities")
    if not isinstance(records,list) or not records:
        raise ValueError("At least one activity required")
    seen=set()
    for item in records:
        key=(item["package_code"],item["activity_code"])
        if key in seen: raise ValueError("Duplicate activity")
        seen.add(key)
        if not item.get("unit"): raise ValueError("Missing unit")
        scope=Decimal(str(item["scope_quantity"]))
        if not scope.is_finite() or scope<=0: raise ValueError("Invalid scope")
        milestones=item["cumulative_plan"]
        if not milestones: raise ValueError("Missing milestones")
        previous=Decimal(0); last=None
        for point in milestones:
            d=date.fromisoformat(point["date"]); q=Decimal(str(point["quantity"]))
            if (last is not None and d<=last) or not q.is_finite() or q<previous or q>scope:
                raise ValueError("Invalid cumulative milestone")
            previous=q; last=d
        if previous!=scope: raise ValueError("Final milestone must equal scope")
    return doc
