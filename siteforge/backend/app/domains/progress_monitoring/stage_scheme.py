"""Explicit approved EPCC stage weighting; never infer missing earned progress."""
from decimal import Decimal, InvalidOperation
STAGES = ('engineering', 'procurement', 'construction', 'commissioning')

def number(value):
    try:
        v = Decimal(str(value))
        return v if v.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None

def validate_weights(weights):
    errors = []
    if not isinstance(weights, dict) or not weights:
        return ['At least one approved stage weight is required.']
    if any(key not in STAGES for key in weights):
        errors.append('Unsupported stage in cross-stage scheme.')
    if not {'engineering', 'procurement', 'construction'}.issubset(weights):
        errors.append('Engineering, Procurement and Construction must all be allocated.')
    if any(type(w) is not int or w < 0 for w in weights.values()):
        errors.append('Weights must be nonnegative integer basis points.')
    if all(type(w) is int for w in weights.values()) and sum(weights.values()) != 10000:
        errors.append('Stage weights must total 10,000 basis points.')
    return errors

def calculate_overall(weights, stages, *, scheme_approved, full_scope, baseline_matches):
    errors = validate_weights(weights)
    if not scheme_approved: errors.append('Cross-stage scheme is not approved.')
    if not full_scope: errors.append('Cross-stage percentage unavailable for restricted scope.')
    if not baseline_matches: errors.append('Stage baselines are not aligned to the approved scheme.')
    values = {}
    for stage, weight in (weights or {}).items():
        info = (stages or {}).get(stage) or {}
        val = number(info.get('percent'))
        if val is None or val < 0 or val > 100 or info.get('status') != 'approved_earned_progress':
            errors.append(f'{stage}: approved source-earned percentage unavailable.')
        else: values[stage] = val
    if errors:return {'percent':None, 'errors':list(dict.fromkeys(errors))}
    result = sum(values[s] * Decimal(weights[s]) for s in weights) / Decimal(10000)
    return {'percent':float(round(result,2)), 'errors':[]}
