"""Select bounded Finance preview evidence without silently collapsing duplicate GRN rows."""


def select_receipt_previews(rows, receipt_ids):
    """Return matching rows exactly once; missing rows remain missing for reconciliation.

    Ambiguous duplicate GRN-line previews must fail closed rather than choose the
    last returned row. No financial certification or posting happens here.
    """
    expected = set(receipt_ids)
    if any(type(rid) is not int or rid <= 0 for rid in expected):
        raise ValueError('Invalid requested receipt line ID')
    selected = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid receipt cost preview row')
        rid = row.get('receipt_line_id')
        if type(rid) is not int or rid <= 0:
            raise ValueError('Invalid receipt cost preview ID')
        if rid in expected:
            if rid in selected:
                raise ValueError('Ambiguous duplicate receipt cost preview')
            selected[rid] = row
    return [selected[rid] for rid in sorted(expected) if rid in selected]
