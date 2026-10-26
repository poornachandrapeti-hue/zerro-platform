"""Approved construction leaf-weight rollups; no inferred cross-stage total."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation

MEASURES = ('reported_percent', 'verified_percent', 'accepted_percent')

def _decimal(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None

def calculate_construction_rollups(rows, target_rows, full_scope):
    """Return measure-specific rollups only for complete, nonduplicated approved leaf weights.

    target_rows may include several reporting periods for the same activity: that
    activity's approved weight must remain identical across all periods.
    """
    errors=[]
    if not full_scope:
        return {'measures':{m:None for m in MEASURES}, 'weights':{}, 'valid_scheme':False,
                'errors':['Project-wide weighted rollup unavailable for scoped or filtered access.']}
    activities={}
    for row in rows:
        aid=row.get('activity_id')
        if aid in activities:
            errors.append('Duplicate Planning leaf activity ID.')
        activities[aid]=row
    weights=defaultdict(set)
    for target in target_rows:
        weights[target.activity_id].add(target.weight_basis_points)
    if not activities:
        errors.append('No linked Planning leaf activities.')
    if set(weights)!=set(activities):
        errors.append('Approved weight coverage differs from Planning leaf activities.')
    if any(len(group)!=1 for group in weights.values()):
        errors.append('Inconsistent approved activity weights across reporting periods.')
    resolved={i:next(iter(values)) for i,values in weights.items() if len(values)==1}
    if any(type(v) is not int or v < 0 for v in resolved.values()) or sum(resolved.values())!=10000:
        errors.append('Approved activity weights must be nonnegative and total 10,000 basis points.')
    source_ids=set()
    for aid,row in activities.items():
        if row.get('link_status')!='linked':
            errors.append('One or more Planning leaf activities lack a valid source mapping.')
        source=row.get('source')
        if isinstance(source,dict) and source.get('construction_activity_id') is not None:
            sid=source['construction_activity_id']
            if sid in source_ids:errors.append('Duplicate Construction source mapping.')
            source_ids.add(sid)
        else:
            errors.append('Missing authoritative Construction source ID.')
    scheme_valid=not errors
    measures={}
    for measure in MEASURES:
        bad=False
        total=Decimal(0)
        for aid,row in activities.items():
            measured=(row.get('measurement') or {}).get(measure)
            value=_decimal(measured)
            if value is None or value<0 or value>100:
                bad=True
            elif aid in resolved:
                total+=value*Decimal(resolved[aid])/Decimal(10000)
        measures[measure]=float(round(total,2)) if scheme_valid and not bad else None
        if bad:errors.append(f'{measure}: missing or invalid source measurement; percentage unavailable.')
    return {'measures':measures,'weights':resolved if scheme_valid else {},
            'valid_scheme':scheme_valid,'errors':list(dict.fromkeys(errors))}
