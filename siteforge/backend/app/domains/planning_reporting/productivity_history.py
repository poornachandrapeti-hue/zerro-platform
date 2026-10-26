"""Read-only retrospective productivity observations, not historic as-of snapshots."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, InvalidOperation


def summarize_daily_lines(lines, unit, end_date, window_days=28):
    """Rows: (work_date, qty, reversal, rework, line_unit, approved_now).

    Approved-now status is deliberately not an approval-as-of-date reconstruction.
    """
    start = end_date - timedelta(days=window_days - 1)
    daily = defaultdict(lambda: Decimal('0'))
    ids = 0
    for day, quantity, reversal, rework, line_unit, approved in lines:
        if not approved or rework or day is None or not start <= day <= end_date:
            continue
        if line_unit != unit:
            return {'status': 'unavailable', 'reason': 'Progress line unit differs from current approved scope unit'}
        try:
            value = Decimal(str(quantity))
        except (InvalidOperation, ValueError, TypeError):
            return {'status': 'unavailable', 'reason': 'Invalid historical progress quantity'}
        if not value.is_finite() or value < 0:
            return {'status': 'unavailable', 'reason': 'Invalid historical progress quantity'}
        daily[day] += (-value if reversal else value)
        ids += 1
    observed = sorted((d,q) for d,q in daily.items() if q != 0)
    positive = [(d,q) for d,q in observed if q > 0]
    if not positive:
        return {'status':'insufficient_data','reason':'No positive verified daily output in selected window', 'days_observed':0}
    total = sum((q for _,q in observed),Decimal('0'))
    if total <= 0:
        return {'status':'insufficient_data','reason':'Net quantity is zero or negative after corrections', 'days_observed':len(positive)}
    # Work-date coverage is not a personnel-hours or rate-per-hour measurement.
    observed_days = len(positive)
    span = (positive[-1][0]-positive[0][0]).days + 1
    coverage = 'broader_sample' if observed_days >= 5 and span >= 14 else 'limited_sample'
    return {'status':'observed','unit':unit,'window_start':start.isoformat(),'window_end':end_date.isoformat(),
        'observed_days':observed_days,'observed_span_days':span,'line_count':ids,
        'net_verified_quantity':float(total),
        'net_quantity_per_observed_day':float((total/Decimal(observed_days)).quantize(Decimal('0.001'))),
        'sample_coverage':coverage,
        'daily':[{'date':d.isoformat(),'net_quantity':float(q)} for d,q in observed],
        'confidence_note':('Broader observed sample' if coverage=='broader_sample' else 'Limited observed sample') + '; not a probability or guaranteed future productivity',
        'basis':'Report work dates with currently approved reports; approvals may have occurred after the work date. Excludes unapproved and rework records. Not verified as-of-date history or a per-hour productivity rate.'}
