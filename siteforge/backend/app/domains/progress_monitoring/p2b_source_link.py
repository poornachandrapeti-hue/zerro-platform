"""P2B: read-only Construction/QA source-link preflight.

The current canonical schema has Construction ProgressReport/ProgressLine and
Quality ConstructionRequest, but the inspection request does not directly
identify a progress report. An explicit verified binding is therefore mandatory.
This module never writes source data or earns/certifies any progress.
"""
from decimal import Decimal, InvalidOperation


def _id(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _qty(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        v = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return v if v.is_finite() and v >= 0 else None


def verify_source_link(*, report, line, inspection, link, organization_id, project_id):
    """Validate explicit source binding using canonical model-like ORM objects.

    Required link fields: report_id, progress_line_id, inspection_request_id,
    binding_verified_by, binding_evidence_ref. The binding MUST come from an
    authoritative source; a caller-constructed activity match is insufficient.
    No indirect assumption of independent review is made here.
    """
    failures = []
    def need(ok, message):
        if not ok:
            failures.append(message)

    need(_id(organization_id) and _id(project_id), 'Invalid scope')
    for name, record in [('Construction report', report), ('QA request', inspection)]:
        need(record is not None and getattr(record, 'organization_id', None) == organization_id
             and getattr(record, 'project_id', None) == project_id, name + ' scope mismatch')
    need(report is not None and getattr(report, 'status', None) == 'Approved', 'Construction report not approved')
    need(inspection is not None and getattr(inspection, 'status', None) == 'Approved', 'QA request not approved')
    need(inspection is not None and getattr(inspection, 'outcome', None) in ('Accepted', 'Partially Accepted'),
         'QA outcome is not accepted')
    need(line is not None and _id(getattr(line, 'id', None)) and
         getattr(line, 'report_id', None) == getattr(report, 'id', None), 'Progress line does not belong to report')
    need(line is not None and _id(getattr(line, 'activity_id', None)) and
         getattr(line, 'activity_id', None) == getattr(inspection, 'activity_id', None), 'Activity mismatch')
    need(isinstance(link, dict) and _id(link.get('report_id')) and
         link.get('report_id') == getattr(report, 'id', None) and
         link.get('progress_line_id') == getattr(line, 'id', None) and
         link.get('inspection_request_id') == getattr(inspection, 'id', None), 'Missing authoritative report-line-inspection binding')
    need(isinstance(link, dict) and _id(link.get('binding_verified_by')) and
         bool(str(link.get('binding_evidence_ref') or '').strip()), 'Binding verification evidence missing')
    accepted = _qty(getattr(inspection, 'accepted_quantity', None))
    construction = _qty(getattr(line, 'quantity', None))
    need(accepted is not None, 'Invalid QA accepted quantity')
    need(construction is not None, 'Invalid Construction line quantity')
    if accepted is not None and construction is not None:
        need(accepted <= construction, 'QA quantity exceeds linked Construction line')
    need(not getattr(line, 'rework', False) and getattr(line, 'reverses_line_id', None) is None,
         'Rework or reversal requires independent reconciliation')
    return {
        'linked': not failures,
        'accepted_quantity': format(accepted, 'f') if not failures else None,
        'report_id': getattr(report, 'id', None) if not failures else None,
        'progress_line_id': getattr(line, 'id', None) if not failures else None,
        'inspection_request_id': getattr(inspection, 'id', None) if not failures else None,
        'reasons': failures,
        'progress_earned': False,
        'billing_certified': False,
    }
