"""P5B4: fail-closed, read-only commercial reconciliation wiring.

Resolver functions are SERVER-OWNED and project scoped. This module never creates
certification, invoice, journal, or published Progress records. A missing Finance
certification owner is a hard error; an empty list is acceptable only when its
canonical source explicitly returns it with authority metadata.
"""
from collections.abc import Callable
from .p5b3_reconciliation import reconcile_certifications, command_center_status


class AuthorityUnavailable(ValueError):
    pass


def _valid_id(value):
    return type(value) is int and value > 0


def _resolve(fn, name, organization_id, project_id, record_id):
    if not isinstance(fn, Callable):
        raise AuthorityUnavailable(f"Canonical {name} resolver unavailable")
    row = fn(organization_id=organization_id, project_id=project_id, record_id=record_id)
    if not isinstance(row, dict):
        raise AuthorityUnavailable(f"Canonical {name} record unavailable")
    if row.get('organization_id') != organization_id or row.get('project_id') != project_id:
        raise AuthorityUnavailable(f"{name} scope mismatch")
    if row.get('server_authorized') is not True:
        raise AuthorityUnavailable(f"{name} must be server-authorized")
    return row


def commercial_readback(*, organization_id, project_id, snapshot_id, contract_id, boq_line_id,
                        fetch_published_snapshot, fetch_contract_boq, fetch_finance_certifications,
                        authorization, evidence_current):
    """Authenticated backend-only readback for potential commercial review.

    `authorization` is trusted server-created permission context, not a client flag.
    Each fetch function must enforce principal/org/project visibility independently.
    """
    if not all(_valid_id(v) for v in (organization_id, project_id, snapshot_id, contract_id, boq_line_id)):
        raise AuthorityUnavailable('Invalid scoped identifier')
    if not isinstance(authorization, dict) or authorization.get('server_checked') is not True or authorization.get('commercial_view') is not True:
        raise AuthorityUnavailable('Commercial read permission not established')
    if authorization.get('organization_id') != organization_id or authorization.get('project_id') != project_id:
        raise AuthorityUnavailable('Authorization scope mismatch')
    if evidence_current is not True:
        raise AuthorityUnavailable('Fresh evidence revalidation required')

    snapshot = _resolve(fetch_published_snapshot, 'published Progress', organization_id, project_id, snapshot_id)
    if snapshot.get('snapshot_id') != snapshot_id or snapshot.get('status') != 'Published' or snapshot.get('publication_persisted') is not True:
        raise AuthorityUnavailable('Published Progress not authoritative')
    if snapshot.get('requires_source_integrity_revalidation') is not False:
        raise AuthorityUnavailable('Published source evidence has not been revalidated')
    if snapshot.get('qa_evidence_authenticated') is not True:
        raise AuthorityUnavailable('Authenticated QA measurement evidence required')

    boq = _resolve(fetch_contract_boq, 'contract BOQ', organization_id, project_id, boq_line_id)
    if boq.get('contract_id') != contract_id or boq.get('boq_line_id') != boq_line_id:
        raise AuthorityUnavailable('Contract/BOQ identity mismatch')
    if boq.get('billing_terms_approved') is not True:
        raise AuthorityUnavailable('Contract billing authority missing')

    if not isinstance(fetch_finance_certifications, Callable):
        raise AuthorityUnavailable('Finance certification source of truth not connected')
    certifications = fetch_finance_certifications(
        organization_id=organization_id, project_id=project_id,
        contract_id=contract_id, boq_line_id=boq_line_id)
    if not isinstance(certifications, dict) or certifications.get('source_authoritative') is not True:
        raise AuthorityUnavailable('Finance source has not confirmed canonical certification history')
    if certifications.get('organization_id') != organization_id or certifications.get('project_id') != project_id or certifications.get('contract_id') != contract_id or certifications.get('boq_line_id') != boq_line_id:
        raise AuthorityUnavailable('Finance certification scope mismatch')
    if certifications.get('complete_history') is not True or certifications.get('reversals_reconciled') is not True:
        raise AuthorityUnavailable('Incomplete certification/reversal history')
    rows = certifications.get('rows')
    if not isinstance(rows, list):
        raise AuthorityUnavailable('Certification rows missing')
    qty = snapshot.get('qa_accepted_quantity_by_boq', {})
    if not isinstance(qty, dict) or str(boq_line_id) not in qty:
        raise AuthorityUnavailable('Missing authoritative QA to BOQ quantity mapping')
    unit = boq.get('unit')
    if not isinstance(unit, str) or not unit.strip() or qty.get(str(boq_line_id)) is None:
        raise AuthorityUnavailable('Contract unit or QA quantity missing')
    if snapshot.get('unit_by_boq', {}).get(str(boq_line_id)) != unit:
        raise AuthorityUnavailable('QA/BOQ unit mismatch')
    if any(row.get('unit') != unit for row in rows if isinstance(row, dict)):
        raise AuthorityUnavailable('Finance/BOQ unit mismatch')

    result = reconcile_certifications(
        organization_id=organization_id, project_id=project_id,
        contract_id=contract_id, boq_line_id=boq_line_id,
        approved_boq_quantity=boq.get('approved_quantity'),
        qa_accepted_quantity=qty[str(boq_line_id)],
        certification_rows=rows, authorized=True, server_revalidated=True)
    result['snapshot_id'] = snapshot_id
    result['commercial_review_only'] = True
    result['requires_finance_owner_final_approval'] = True
    return result


def safe_command_center_projection(*, organization_id, project_id, snapshot, reconciliation,
                                   authorization, evidence_current):
    if not isinstance(authorization, dict) or authorization.get('server_checked') is not True or authorization.get('dashboard_view') is not True:
        raise AuthorityUnavailable('Dashboard permission missing')
    if (authorization.get('organization_id'), authorization.get('project_id')) != (organization_id, project_id):
        raise AuthorityUnavailable('Dashboard authorization scope mismatch')
    return command_center_status(organization_id=organization_id, project_id=project_id,
                                 published_snapshot=snapshot, reconciliation=reconciliation,
                                 authorized=True, evidence_current=evidence_current)
