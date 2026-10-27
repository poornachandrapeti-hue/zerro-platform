"""P5 read-only commercial boundary for Progress.

Caller MUST supply values from server-side authorized database readbacks. This module
is not an authentication boundary and never creates invoices, certificates, or GL.
Unpublished P3 previews are explicitly not eligible for a billing handoff.
"""
from decimal import Decimal, InvalidOperation


class CommercialBoundaryError(ValueError):
    pass


def _quantity(value):
    if isinstance(value, bool):
        raise CommercialBoundaryError("Invalid boolean quantity")
    try:
        value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CommercialBoundaryError("Invalid quantity") from exc
    if not value.is_finite() or value < 0:
        raise CommercialBoundaryError("Quantity must be nonnegative and finite")
    return value


def inspect_commercial_handoff(*, progress, contract, organization_id, project_id,
                               authorized, server_revalidated):
    """Return read-only eligibility assessment; never authorize billing or payment."""
    if authorized is not True or server_revalidated is not True:
        raise CommercialBoundaryError("Server authorization and fresh source validation required")
    if not isinstance(progress, dict) or not isinstance(contract, dict):
        raise CommercialBoundaryError("Canonical progress and contract records required")
    for record in (progress, contract):
        if (record.get("organization_id"), record.get("project_id")) != (organization_id, project_id):
            raise CommercialBoundaryError("Cross-scope authority")
        if record.get("server_authorized") is not True:
            raise CommercialBoundaryError("Missing server-grounded source")
    if progress.get("status") != "Published" or progress.get("published") is not True:
        raise CommercialBoundaryError("Only persisted Published snapshots may enter commercial review")
    if progress.get("publication_persisted") is not True or progress.get("approval_audit_valid") is not True:
        raise CommercialBoundaryError("Published snapshot lacks persisted audit authority")
    if progress.get("source_integrity_valid") is not True or progress.get("revoked") is True:
        raise CommercialBoundaryError("Measurement evidence invalid or revoked")
    if contract.get("status") != "Active" or contract.get("billing_terms_approved") is not True:
        raise CommercialBoundaryError("Contract is not approved for billing review")
    if not progress.get("snapshot_id") or not progress.get("revision_id") or not contract.get("contract_id"):
        raise CommercialBoundaryError("Missing immutable source identifiers")
    if progress.get("contract_id") != contract.get("contract_id"):
        raise CommercialBoundaryError("Contract reference mismatch")
    if progress.get("work_package_id") != contract.get("work_package_id"):
        raise CommercialBoundaryError("Work package mismatch")
    unit = progress.get("unit")
    if not unit or unit != contract.get("unit"):
        raise CommercialBoundaryError("Quantity unit mismatch")
    published_qty = _quantity(progress.get("qa_accepted_quantity"))
    verified_qty = _quantity(progress.get("independently_verified_quantity"))
    contracted_qty = _quantity(contract.get("approved_quantity"))
    previously_certified = _quantity(contract.get("previously_certified_quantity"))
    if not (published_qty <= verified_qty <= contracted_qty):
        raise CommercialBoundaryError("Quantity authority hierarchy violated")
    if previously_certified > published_qty:
        raise CommercialBoundaryError("Already certified quantity exceeds accepted quantity")
    remaining = published_qty - previously_certified
    return {
        "status": "REVIEW_CANDIDATE_ONLY",
        "organization_id": organization_id,
        "project_id": project_id,
        "snapshot_id": progress["snapshot_id"],
        "revision_id": progress["revision_id"],
        "contract_id": contract["contract_id"],
        "work_package_id": progress["work_package_id"],
        "unit": unit,
        "maximum_reviewable_quantity": str(remaining),
        "billing_certified": False,
        "invoice_created": False,
        "finance_posted": False,
        "warning": "Requires commercial officer certification, reconciliation and authoritative Contract/Finance posting",
    }


def command_center_progress_view(*, snapshot, organization_id, project_id,
                                 authorized, server_revalidated):
    """Conservative read-only dashboard projection; no billing or earning inference."""
    if authorized is not True or server_revalidated is not True:
        raise CommercialBoundaryError("Unauthorized dashboard readback")
    if not isinstance(snapshot, dict) or (snapshot.get("organization_id"),snapshot.get("project_id")) != (organization_id, project_id):
        raise CommercialBoundaryError("Invalid dashboard scope")
    if snapshot.get("server_authorized") is not True:
        raise CommercialBoundaryError("Untrusted dashboard source")
    state = snapshot.get("status")
    if state not in ("Draft", "Pending", "Approved", "Published", "Rejected", "Superseded"):
        raise CommercialBoundaryError("Unknown publication status")
    measures = snapshot.get("measures")
    if not isinstance(measures, dict):
        raise CommercialBoundaryError("Measures missing")
    output = {}
    for key in ("reported_percent", "verified_percent", "accepted_percent"):
        val = _quantity(measures.get(key))
        if val > 100:
            raise CommercialBoundaryError("Percentage outside 0-100")
        output[key] = float(val)
    if not (output["accepted_percent"] <= output["verified_percent"] <= output["reported_percent"]):
        raise CommercialBoundaryError("Progress measures inconsistent")
    return {
        "organization_id": organization_id,
        "project_id": project_id,
        "status": state,
        "measures": output,
        "is_published": state == "Published" and snapshot.get("publication_persisted") is True,
        "earned_percent": None,
        "billing_certified": False,
        "source_snapshot_id": snapshot.get("snapshot_id"),
    }
