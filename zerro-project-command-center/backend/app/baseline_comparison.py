"""Conservative approved quantity baseline evaluator. Import is server-controlled, never client-authoritative."""
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


def load_approved_document(document: dict, project_code: str):
    return _validate_approved_document(document, project_code)

def load_approved_manifest(path: str, project_code: str):
    if not path:
        return None
    document = json.loads(Path(path).read_text(encoding='utf-8'))
    return _validate_approved_document(document, project_code)

def _validate_approved_document(document, project_code):
    if not isinstance(document, dict) or document.get('project_code') != project_code:
        raise ValueError('Baseline project does not match')
    if document.get('approval_status') != 'approved' or not all(document.get(k) for k in ('approval_reference', 'approved_by', 'approved_on', 'revision')):
        raise ValueError('An approved revision and approval provenance are mandatory')
    date.fromisoformat(document['approved_on'])
    records = document.get('activities')
    if not isinstance(records, list) or not records:
        raise ValueError('Approved baseline activities missing')
    mapped = {}
    for record in records:
        key = (str(record['package_code']), str(record['activity_code']))
        if key in mapped:
            raise ValueError('Duplicate activity baseline')
        unit = record['unit']
        if not isinstance(unit, str) or not unit.strip():
            raise ValueError('Missing unit')
        scope = Decimal(str(record['scope_quantity']))
        if not scope.is_finite() or scope <= 0:
            raise ValueError('Invalid baseline scope')
        milestones = record['cumulative_plan']
        if not isinstance(milestones, list) or not milestones:
            raise ValueError('Missing dated quantities')
        seen = set()
        previous = Decimal(0)
        points = []
        for point in milestones:
            on = date.fromisoformat(point['date'])
            quantity = Decimal(str(point['quantity']))
            if on in seen or (points and on <= points[-1][0]) or not quantity.is_finite() or quantity < previous or quantity > scope:
                raise ValueError('Invalid cumulative baseline milestone')
            points.append((on, quantity))
            previous = quantity
            seen.add(on)
        if previous != scope:
            raise ValueError('Final planned quantity must equal baseline scope')
        mapped[key] = {'scope':scope, 'unit':unit, 'milestones':points}
    return document, mapped


def apply_baseline(packages, manifest, as_of: date, threshold_pp: float):
    if manifest is None:
        return [], 'not_configured'
    document, mapped = manifest
    try:
        approval_day = date.fromisoformat(document['approved_on'])
    except (KeyError, ValueError) as error:
        raise ValueError('Invalid approval date') from error
    if approval_day > as_of:
        raise ValueError('Baseline is not approved as of the progress snapshot')
    alerts = []
    for pkg in packages:
        for activity in pkg.get('activities', []):
            activity['baseline_status'] = 'unmatched'
            key = (str(pkg['package_code']), str(activity['activity_code']))
            record = mapped.get(key)
            if record is None:
                continue
            try:
                scope = Decimal(str(activity['scope_quantity']))
                actual = Decimal(str(activity['verified_quantity']))
            except (InvalidOperation, ValueError):
                continue
            if not scope.is_finite() or not actual.is_finite() or scope != record['scope'] or activity.get('unit') != record['unit'] or actual < 0:
                activity['baseline_status'] = 'scope_or_unit_mismatch'
                continue
            # Stepwise approved cumulative curve. No unapproved interpolation.
            planned = Decimal(0)
            for milestone_date, quantity in record['milestones']:
                if milestone_date <= as_of:
                    planned = quantity
                else:
                    break
            planned_pct = float(100 * planned / scope)
            actual_pct = float(100 * actual / scope)
            delta = round(actual_pct - planned_pct, 2)
            activity.update(baseline_status='approved', planned_quantity=float(planned), planned_percent=round(planned_pct,2), variance_pp=delta)
            if delta < -threshold_pp:
                alerts.append({'package_code':pkg['package_code'], 'activity_code':activity['activity_code'], 'discipline':pkg['discipline_name'], 'variance_pp':delta, 'level':'behind_plan', 'message':'Verified progress below approved cumulative baseline'})
    return alerts, 'approved_revision'
