"""P4/P5B2: read-only canonical Progress report and Contracts evidence.

No billing authorization or source reclassification. Caller must enforce project RBAC
before invoking these functions. They run in the caller's SQLAlchemy transaction.
"""
from sqlalchemy import select
from .reports_models import ProgressReport, ProgressReportEvent
from app.domains.contracts.models import Contract, ContractVersion, ContractBoq


class SourceAuthorityError(ValueError):
    pass


def _id(value, label):
    if type(value) is not int or value <= 0:
        raise SourceAuthorityError(f"Invalid {label}")
    return value


def _authorized(flag):
    if flag is not True:
        raise SourceAuthorityError("Server-side project permission required")


def published_report_readback(db, *, organization_id, project_id, report_id, authorized):
    """Read existing persisted publication only; never manufacture certification."""
    _authorized(authorized)
    for label, value in (("organization", organization_id), ("project", project_id), ("report", report_id)):
        _id(value, label)
    report = db.execute(select(ProgressReport).where(
        ProgressReport.id == report_id,
        ProgressReport.organization_id == organization_id,
        ProgressReport.project_id == project_id,
    )).scalar_one_or_none()
    if report is None:
        raise SourceAuthorityError("Progress report not found in project")
    if report.status != "Published" or report.published_at is None or not isinstance(report.snapshot, dict):
        raise SourceAuthorityError("No authoritative published report snapshot")
    events = db.execute(select(ProgressReportEvent).where(
        ProgressReportEvent.report_id == report.id,
        ProgressReportEvent.organization_id == organization_id,
        ProgressReportEvent.project_id == project_id,
    ).order_by(ProgressReportEvent.id)).scalars().all()
    if not events or not any(str(e.event).lower() in {"publish", "published"} for e in events):
        raise SourceAuthorityError("Publication audit event missing")
    if report.prepared_by == report.approver_id:
        raise SourceAuthorityError("Independent report approver missing")
    return {
        "organization_id": organization_id, "project_id": project_id,
        "snapshot_id": report.id, "report_number": report.report_number,
        "revision": report.revision, "status": report.status,
        "published_at": report.published_at.isoformat(),
        "source_cutoff": report.source_cutoff.isoformat() if report.source_cutoff else None,
        "snapshot": report.snapshot,
        "publication_persisted": True, "publication_event_count": len(events),
        # Explicitly refuse to infer certification, QA approval, or invoice eligibility.
        "billing_certified": False, "commercial_review_eligible": False,
        "requires_source_integrity_revalidation": True,
        "server_authorized": True,
    }


def contract_boq_readback(db, *, organization_id, project_id, contract_id, boq_line_id, authorized):
    """Project-scoped published Contract/BOQ identity; no finance ledger writes."""
    _authorized(authorized)
    for label, value in (("organization", organization_id), ("project", project_id),
                         ("contract", contract_id), ("BOQ line", boq_line_id)):
        _id(value, label)
    contract = db.execute(select(Contract).where(
        Contract.id == contract_id, Contract.organization_id == organization_id,
        Contract.project_id == project_id,
    )).scalar_one_or_none()
    if contract is None or contract.published_version is None:
        raise SourceAuthorityError("No published contract version")
    if contract.lifecycle not in {"Active", "Executed", "InExecution"}:
        raise SourceAuthorityError("Contract not in execution")
    version = db.execute(select(ContractVersion).where(
        ContractVersion.contract_id == contract.id,
        ContractVersion.version == contract.published_version,
    )).scalar_one_or_none()
    if version is None or version.state not in {"Published", "Executed", "Approved"}:
        raise SourceAuthorityError("Published contract version not authoritative")
    line = db.execute(select(ContractBoq).where(
        ContractBoq.id == boq_line_id, ContractBoq.contract_id == contract.id,
        ContractBoq.version_id == version.id,
    )).scalar_one_or_none()
    if line is None:
        raise SourceAuthorityError("BOQ line not in published contract version")
    return {
        "organization_id": organization_id, "project_id": project_id,
        "contract_id": contract.id, "published_version": contract.published_version,
        "contract_version_id": version.id, "boq_line_id": line.id,
        "boq_code": line.code, "unit": line.unit, "approved_quantity": str(line.quantity),
        "currency": line.currency, "server_authorized": True,
        "billing_terms_approved": False, # requires separate authority
        "previously_certified_quantity": None, # MUST query Finance owner
        "commercial_review_eligible": False,
    }
