"""Catalogue export aligned with the Excel import template for round-trip use.

Import ignores unknown columns, so approval_status / active / version stay at the
end for reporting without blocking re-import.
"""
import csv
import io
import json
from openpyxl import Workbook

# Same order as service.item_template() so Export Excel can be edited and re-imported.
IMPORT_COLUMNS = (
    "code",
    "description",
    "type",
    "category",
    "subcategory",
    "disciplines",
    "specification",
    "size",
    "material_grade",
    "standard",
    "unit",
    "purchase_unit",
    "issue_unit",
    "make",
    "model",
    "mpn",
    "hsn",
    "inspection",
    "tracking",
    "mtc",
    "calibration",
    "shelf_life",
    "shelf_life_days",
    "specification_attributes",
)

# Informational columns appended for export only (import ignores them).
EXPORT_STATUS_COLUMNS = ("approval_status", "active", "version")
EXPORT_COLUMNS = IMPORT_COLUMNS + EXPORT_STATUS_COLUMNS


def is_approved_item(item):
    return bool(item and item.active and item.approval_status == "Approved")


def _yes_no(value):
    return "yes" if bool(value) else "no"


def exchange_row(item, discipline_names):
    """Map a ProcurementItem (+ discipline names) into import-compatible fields."""
    base = getattr(item, "base_unit", "") or ""
    purchase = (getattr(item, "purchase_unit", "") or "").strip() or base
    issue = (getattr(item, "issue_unit", "") or "").strip() or base
    attributes = getattr(item, "specification_attributes", None) or {}
    return {
        "code": item.code,
        "description": item.description,
        "type": item.item_type,
        "category": item.category or "",
        "subcategory": getattr(item, "subcategory", "") or "",
        "disciplines": ", ".join(discipline_names or []),
        "specification": item.specification or "",
        "size": item.size_rating or "",
        "material_grade": getattr(item, "material_grade", "") or "",
        "standard": getattr(item, "applicable_standard", "") or "",
        "unit": base,
        "purchase_unit": purchase,
        "issue_unit": issue,
        "make": item.approved_make or "",
        "model": getattr(item, "model_number", "") or "",
        "mpn": getattr(item, "manufacturer_part_number", "") or "",
        "hsn": getattr(item, "hsn_code", "") or "",
        "inspection": _yes_no(item.inspection_required),
        "tracking": _yes_no(item.tracking_required),
        "mtc": _yes_no(getattr(item, "mtc_required", False)),
        "calibration": _yes_no(getattr(item, "calibration_certificate_required", False)),
        "shelf_life": _yes_no(getattr(item, "shelf_life_applicable", False)),
        "shelf_life_days": getattr(item, "shelf_life_days", None) or "",
        "specification_attributes": json.dumps(attributes, sort_keys=True, ensure_ascii=False),
        "approval_status": item.approval_status,
        "active": "yes" if item.active else "no",
        "version": item.version,
    }


def rows_from_items(db, items):
    from app.domains.identity_projects.models import Discipline

    cache = {}
    rows = []
    for item in items:
        names = []
        for discipline_id in item.discipline_ids or []:
            if discipline_id not in cache:
                row = db.get(Discipline, discipline_id)
                cache[discipline_id] = row.name if row else ""
            if cache[discipline_id]:
                names.append(cache[discipline_id])
        rows.append(exchange_row(item, names))
    return rows


def export_catalogue_csv(items_or_rows):
    """Accept ORM items (legacy tests) or already-mapped exchange dict rows."""
    rows = []
    for entry in items_or_rows:
        if isinstance(entry, dict):
            rows.append(entry)
        else:
            rows.append(exchange_row(entry, []))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for record in rows:
        writer.writerow({name: record.get(name, "") for name in EXPORT_COLUMNS})
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def export_catalogue_xlsx(rows):
    """Workbook using import columns first so the file can be re-imported after edits."""
    book = Workbook()
    sheet = book.active
    sheet.title = "Catalogue"
    sheet.append(list(EXPORT_COLUMNS))
    for record in rows:
        sheet.append([record.get(name, "") for name in EXPORT_COLUMNS])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()
