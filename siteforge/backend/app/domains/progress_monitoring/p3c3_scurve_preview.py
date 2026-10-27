"""P3C3: chronological S-curve and discipline previews, never publication."""
from datetime import date
from decimal import Decimal
from .p3c2_integration_gate import gated_preview, ProgressAuthorityError


def scurve_preview(*, periods, organization_id, project_id, authorized, full_scope):
    if not periods: raise ProgressAuthorityError('No reporting periods')
    output=[]; last_date=None; prior={}
    for period in periods:
        try: day=date.fromisoformat(period['as_of'])
        except (KeyError,ValueError,TypeError): raise ProgressAuthorityError('Invalid as_of date')
        if last_date is not None and day<=last_date: raise ProgressAuthorityError('Periods must be strictly chronological')
        last_date=day
        result=gated_preview(authority_rows=period['authority_rows'],target_rows=period['target_rows'],
                  organization_id=organization_id,project_id=project_id,authorized=authorized,full_scope=full_scope)
        measures=result['measures']
        if any(Decimal(str(v))<Decimal(str(prior.get(k,0))) for k,v in measures.items()):
            raise ProgressAuthorityError('Regressive cumulative measures require a separate revision workflow')
        if not (measures['accepted_percent']<=measures['verified_percent']<=measures['reported_percent']):
            raise ProgressAuthorityError('Invalid cumulative ordering')
        prior=measures
        output.append({'as_of':day.isoformat(),**measures,'status':'UNPUBLISHED_PREVIEW'})
    return {'series':output,'published':False,'earned_percent':None,'billing_certified':False}


def discipline_preview(*, disciplines, organization_id, project_id, authorized):
    if authorized is not True: raise ProgressAuthorityError('Authorization required')
    if not isinstance(disciplines,dict) or not disciplines: raise ProgressAuthorityError('Disciplines required')
    result={}
    for discipline,scoped in disciplines.items():
        if not discipline or not isinstance(scoped,dict): raise ProgressAuthorityError('Invalid discipline')
        result[discipline]=gated_preview(authority_rows=scoped['authority_rows'],target_rows=scoped['target_rows'],
                        organization_id=organization_id,project_id=project_id,authorized=True,full_scope=True)['measures']
    return {'disciplines':result,'status':'UNPUBLISHED_PREVIEW','project_total':None}
