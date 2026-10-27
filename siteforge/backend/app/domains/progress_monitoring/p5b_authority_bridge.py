"""Fail-closed P5B read-only orchestration.

The caller supplies *trusted server-side* resolver functions; untrusted frontend
payloads must never be passed as canonical records. This does not certify bills.
"""
from collections.abc import Callable
from .p5_commercial_boundary import (
    CommercialBoundaryError, inspect_commercial_handoff,
    command_center_progress_view,
)


def _id(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CommercialBoundaryError(f"Invalid {label}")
    return value


def _source(resolver, *, name, organization_id, project_id, record_id):
    if not isinstance(record_id, (int, str)) or isinstance(record_id, bool) or not str(record_id).strip():
        raise CommercialBoundaryError(f"Invalid {name} identifier")
    if not isinstance(resolver, Callable):
        raise CommercialBoundaryError(f"Missing server resolver for {name}")
    record = resolver(organization_id=organization_id, project_id=project_id, record_id=record_id)
    if not isinstance(record, dict):
        raise CommercialBoundaryError(f"Missing authoritative {name} record")
    if (record.get('organization_id'), record.get('project_id')) != (organization_id, project_id):
        raise CommercialBoundaryError(f"Cross-project {name} record")
    if record.get('server_authorized') is not True:
        raise CommercialBoundaryError(f"Untrusted {name} resolver result")
    return record


def commercial_review_from_sources(*, organization_id, project_id, snapshot_id,
                                   contract_id, fetch_snapshot, fetch_contract,
                                   can_review, evidence_current, certification_current):
    """Read-only *candidate*; certifier must recheck against canonical posting owner.

    Source resolvers must be injected from authenticated backend handlers and must
    enforce caller role, organization and project themselves. Boolean guards are
    additional fail-closed assertions, not substitutes for middleware or database RBAC.
    """
    _id(organization_id, 'organization'); _id(project_id, 'project')
    if can_review is not True or evidence_current is not True or certification_current is not True:
        raise CommercialBoundaryError('Fresh authorization, evidence and certification reads required')
    progress = _source(fetch_snapshot, name='snapshot', organization_id=organization_id,
                       project_id=project_id, record_id=snapshot_id)
    contract = _source(fetch_contract, name='contract', organization_id=organization_id,
                       project_id=project_id, record_id=contract_id)
    if str(progress.get('snapshot_id')) != str(snapshot_id) or str(contract.get('contract_id')) != str(contract_id):
        raise CommercialBoundaryError('Source identity mismatch')
    result = inspect_commercial_handoff(progress=progress, contract=contract,
                organization_id=organization_id, project_id=project_id,
                authorized=True, server_revalidated=True)
    result['persistent_certification_created'] = False
    result['requires_contracts_finance_reconciliation'] = True
    return result


def dashboard_from_source(*, organization_id, project_id, snapshot_id, fetch_snapshot,
                          can_view, evidence_current):
    """Read-only Command Center projection; never exposes draft as billable."""
    _id(organization_id, 'organization'); _id(project_id, 'project')
    if can_view is not True or evidence_current is not True:
        raise CommercialBoundaryError('Dashboard authorization or source freshness missing')
    snapshot = _source(fetch_snapshot, name='snapshot', organization_id=organization_id,
                       project_id=project_id, record_id=snapshot_id)
    if str(snapshot.get('snapshot_id')) != str(snapshot_id):
        raise CommercialBoundaryError('Snapshot identity mismatch')
    return command_center_progress_view(snapshot=snapshot, organization_id=organization_id,
                                        project_id=project_id, authorized=True, server_revalidated=True)
