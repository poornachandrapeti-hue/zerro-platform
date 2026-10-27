"""P3C2 read-only gate: require server-grounded leaf authorities before WBS previews.

Caller must construct evidence from canonical Planning, Construction, QA and document readbacks.
Never use user-provided booleans as proof; no publication or billing side effects.
"""
from decimal import Decimal, InvalidOperation
from .p3c2_wbs_preview import preview_wbs, ProgressPreviewError

class ProgressAuthorityError(ValueError):
    pass

def dec(v):
    if isinstance(v, bool): raise ProgressAuthorityError('Boolean is not a quantity')
    try: r=Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError): raise ProgressAuthorityError('Invalid quantity')
    if not r.is_finite() or r<0: raise ProgressAuthorityError('Non-finite or negative quantity')
    return r

def gated_preview(*, authority_rows, target_rows, organization_id, project_id, authorized, full_scope):
    if authorized is not True or full_scope is not True:
        raise ProgressAuthorityError('Project-wide server authorization required')
    if not authority_rows: raise ProgressAuthorityError('Missing authoritative leaves')
    leaves=[]; used=set()
    for row in authority_rows:
        if not isinstance(row,dict) or row.get('server_authorized') is not True or row.get('source_revalidated') is not True:
            raise ProgressAuthorityError('Unverified server-side evidence')
        if (row.get('organization_id'),row.get('project_id')) != (organization_id, project_id):
            raise ProgressAuthorityError('Cross-project leaf')
        aid=row.get('activity_id')
        if aid is None or aid in used: raise ProgressAuthorityError('Missing or duplicate leaf')
        used.add(aid)
        if row.get('baseline_approved') is not True or row.get('construction_verified') is not True or row.get('qa_evidence_approved') is not True or row.get('attachment_authenticated') is not True:
            raise ProgressAuthorityError('Incomplete verified provenance')
        planned=dec(row.get('planned_quantity'))
        reported=dec(row.get('reported_quantity'))
        verified=dec(row.get('verified_quantity'))
        accepted=dec(row.get('accepted_quantity'))
        if planned<=0 or not (accepted<=verified<=reported<=planned):
            raise ProgressAuthorityError('Quantity hierarchy violated')
        if not row.get('unit') or row.get('unit')!=row.get('verified_unit') or row.get('unit')!=row.get('qa_unit'):
            raise ProgressAuthorityError('Unit mismatch')
        if not row.get('construction_activity_id') or not row.get('verification_id') or not row.get('inspection_id') or not row.get('attachment_id'):
            raise ProgressAuthorityError('Missing canonical provenance ID')
        leaves.append({'activity_id':aid,'approved_baseline':True,'measurement_valid':True,'link_status':'linked',
                       'source':{'construction_activity_id':row['construction_activity_id']},
                       'measurement':{'reported_percent':float(reported/planned*100),
                                      'verified_percent':float(verified/planned*100),
                                      'accepted_percent':float(accepted/planned*100)}})
    try:
        result=preview_wbs(leaves=leaves,approved_targets=target_rows,full_scope=True,authorized=True,association_evidence_complete=True)
    except ProgressPreviewError as exc:
        raise ProgressAuthorityError(str(exc)) from exc
    return {**result,'authority':'SERVER_GROUNDED_READ_ONLY','publication_eligible':False}
