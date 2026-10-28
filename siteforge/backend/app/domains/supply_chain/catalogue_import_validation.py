"""Pure validation helpers for organization-scoped catalogue Excel imports."""

MAX_IMPORT_ROWS = 1000


def duplicate_codes(header, rows):
    """Return duplicate physical worksheet rows, normalized case/whitespace.

    All occurrences, including the first, are flagged to avoid ambiguous
    order-dependent confirmation or updates. Blank rows are ignored.
    """
    if "code" not in header:
        return {}
    code_index = header.index("code")
    seen = {}
    for number, row in enumerate(rows, start=2):
        if not any(cell not in (None, "") for cell in row):
            continue
        value = row[code_index] if code_index < len(row) else None
        key = str(value).strip().casefold() if value is not None else ""
        if key:
            seen.setdefault(key, []).append(number)
    return {index: tuple(indices) for indices in seen.values() if len(indices) > 1 for index in indices}
