"""P3C2: calculate WBS previews from approved weights and authoritative leaf results.

No earning, publication or billing side effects. Does not infer absent verification.
"""
from .rollup import calculate_construction_rollups

class ProgressPreviewError(ValueError):
    pass

def preview_wbs(*, leaves, approved_targets, full_scope, authorized, association_evidence_complete):
    if authorized is not True or full_scope is not True:
        raise ProgressPreviewError('Whole-project authorized access required')
    if association_evidence_complete is not True:
        raise ProgressPreviewError('Authoritative site measurement and QA links incomplete')
    if not isinstance(leaves,list) or not leaves:
        raise ProgressPreviewError('Planning leaves required')
    if not isinstance(approved_targets,(list,tuple)) or not approved_targets:
        raise ProgressPreviewError('Approved weight targets required')
    for leaf in leaves:
        if not isinstance(leaf,dict) or leaf.get('approved_baseline') is not True:
            raise ProgressPreviewError('Approved Planning baseline required for every leaf')
        if leaf.get('measurement_valid') is not True:
            raise ProgressPreviewError('Independently verified leaf measurement required')
    result=calculate_construction_rollups(leaves,approved_targets,full_scope=True)
    if not result['valid_scheme'] or result['errors'] or any(v is None for v in result['measures'].values()):
        raise ProgressPreviewError('WBS rollup invalid: '+'; '.join(result['errors']))
    return {'status':'UNPUBLISHED_PREVIEW','measures':result['measures'],
            'weights':result['weights'],'earned_percent':None,
            'billable_quantity':None,'published':False,'billing_certified':False}
