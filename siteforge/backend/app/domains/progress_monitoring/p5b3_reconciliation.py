"""P5B3 read-only Finance certification reconciliation for Progress.

Inputs MUST be assembled by authenticated server-side DB adapters. This file does
not identify a canonical Finance certificate owner or certify any quantity.
"""
from decimal import Decimal, InvalidOperation

class ReconciliationError(ValueError):
    pass

def _id(v, name):
    if type(v) is not int or v <= 0:
        raise ReconciliationError(f"Invalid {name}")

def _qty(v, name):
    if isinstance(v, bool) or v is None:
        raise ReconciliationError(f"Invalid {name}")
    try: d = Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError) as e: raise ReconciliationError(f"Invalid {name}") from e
    if not d.is_finite() or d < 0: raise ReconciliationError(f"Invalid {name}")
    return d

def reconcile_certifications(*, organization_id, project_id, contract_id, boq_line_id,
                             approved_boq_quantity, qa_accepted_quantity,
                             certification_rows, authorized, server_revalidated):
    """Conservative quantity reconciliation, NOT a bill or release authorization.

    Each certification row must be read by the Finance/Contracts owner, scoped to
    the same organization, project, contract, BOQ line, and unit. Only explicitly
    posted/approved canonical rows are included; pending/revoked rows cause a
    fail-closed error because their effect on net certification is not established.
    """
    if authorized is not True or server_revalidated is not True:
        raise ReconciliationError("Fresh server-side authorization and readback required")
    for k,v in [('organization',organization_id),('project',project_id),('contract',contract_id),('BOQ line',boq_line_id)]: _id(v,k)
    boq = _qty(approved_boq_quantity,'BOQ quantity')
    qa = _qty(qa_accepted_quantity,'QA accepted quantity')
    if qa > boq: raise ReconciliationError('Accepted quantity exceeds approved BOQ quantity')
    if not isinstance(certification_rows,list): raise ReconciliationError('Authoritative certification list required')
    seen=set(); total=Decimal('0'); unit=None
    for row in certification_rows:
        if not isinstance(row,dict) or row.get('server_authorized') is not True: raise ReconciliationError('Untrusted certification row')
        for key, expected in [('organization_id',organization_id),('project_id',project_id),('contract_id',contract_id),('boq_line_id',boq_line_id)]:
            if row.get(key)!=expected: raise ReconciliationError(f'Certification scope mismatch: {key}')
        rid=row.get('certification_id')
        if not isinstance(rid,(str,int)) or isinstance(rid,bool) or not str(rid).strip() or rid in seen: raise ReconciliationError('Missing or duplicate certification identity')
        seen.add(rid)
        if row.get('status') not in {'Approved','Posted'}: raise ReconciliationError('Unresolved certification status')
        if row.get('revoked') is True: raise ReconciliationError('Revoked certification requires authoritative net reconciliation')
        if not row.get('unit'): raise ReconciliationError('Certification unit missing')
        if unit is None: unit=row['unit']
        if row['unit']!=unit: raise ReconciliationError('Certification unit mismatch')
        total+=_qty(row.get('quantity'),'certified quantity')
    if total>qa: raise ReconciliationError('Already certified quantity exceeds accepted quantity')
    return {'status':'READ_ONLY_RECONCILIATION','organization_id':organization_id,'project_id':project_id,
        'contract_id':contract_id,'boq_line_id':boq_line_id,'certification_count':len(seen),
        'previously_certified_quantity':str(total),'remaining_candidate_quantity':str(qa-total),
        'billing_certified':False,'invoice_created':False,'finance_posted':False,
        'requires_canonical_owner_validation':True}

def command_center_status(*, organization_id, project_id, published_snapshot,
                          reconciliation, authorized, evidence_current):
    """Show read-only project status; withhold billing amounts and earned progress."""
    if authorized is not True or evidence_current is not True: raise ReconciliationError('Unauthorized or stale dashboard')
    _id(organization_id,'organization');_id(project_id,'project')
    if not isinstance(published_snapshot,dict) or not isinstance(reconciliation,dict): raise ReconciliationError('Missing source projection')
    for source in (published_snapshot,reconciliation):
        if (source.get('organization_id'),source.get('project_id'))!=(organization_id,project_id): raise ReconciliationError('Cross-project dashboard data')
    if published_snapshot.get('status')!='Published' or published_snapshot.get('publication_persisted') is not True:
        raise ReconciliationError('Authoritative publication missing')
    if reconciliation.get('status')!='READ_ONLY_RECONCILIATION': raise ReconciliationError('Untrusted reconciliation')
    return {'organization_id':organization_id,'project_id':project_id,'snapshot_id':published_snapshot.get('snapshot_id'),
            'status':'Published','commercial_review':'NOT_CERTIFIED','earned_progress':None,
            'billing_certified':False,'finance_posted':False}
