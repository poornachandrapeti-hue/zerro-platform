"""Hard bounds for read-only Stores -> Finance movement evidence requests.

Fail closed rather than returning a misleading partial valuation from a truncated
set of receipt lots or acceptance movements.  This module performs no writes.
"""

MAX_ISSUE_LOT_ALLOCATIONS = 256
MAX_ACCEPTANCE_POSTINGS_PER_RECEIPT = 512


def require_complete_bounded_rows(rows, maximum, label):
    """A caller fetches maximum+1 rows and rejects oversize evidence.

    Do not silently trim a ledger snapshot: dropping rows would make a cost or
    historical stock calculation look complete when it is not.
    """
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0:
        raise ValueError('Invalid bounded evidence limit')
    if not isinstance(rows, (list, tuple)):
        raise ValueError('Expected materialized evidence rows')
    if len(rows) > maximum:
        raise ValueError(f'{label} exceeds bounded evidence capacity ({maximum})')
    return rows
