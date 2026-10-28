"""Read-only, stable catalogue export and downstream item eligibility checks."""
import csv
import io
import json

EXPORT_COLUMNS = ("code", "description", "item_type", "category", "base_unit", "approval_status", "active", "specification", "specification_attributes", "size_rating", "approved_make", "inspection_required", "tracking_required", "version")


def is_approved_item(item):
    return bool(item and item.active and item.approval_status == "Approved")


def export_catalogue_csv(items):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        record = {name: getattr(item, name, None) for name in EXPORT_COLUMNS}
        record["specification_attributes"] = json.dumps(record["specification_attributes"] or {}, sort_keys=True, ensure_ascii=False)
        writer.writerow(record)
    return ("\ufeff" + output.getvalue()).encode("utf-8")
