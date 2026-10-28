import csv
import io
import json
from types import SimpleNamespace
from app.domains.supply_chain.catalogue_exchange import (EXPORT_COLUMNS, export_catalogue_csv, is_approved_item)


def sample(status="Approved", active=True):
    return SimpleNamespace(code="MEC-001", description="Pump", item_type="Equipment", category="Pumps", base_unit="Nos",
        approval_status=status, active=active, specification="50 m3/h", specification_attributes={"flow": 50, "head": "30 m"},
        size_rating="", approved_make="", inspection_required=True, tracking_required=False, version=2)


def test_only_approved_active_item_is_eligible():
    assert is_approved_item(sample())
    for status in ("Draft", "Pending Approval", "Rejected", None):
        assert not is_approved_item(sample(status=status))
    assert not is_approved_item(sample(active=False))
    assert not is_approved_item(None)


def test_export_has_stable_columns_and_json():
    raw = export_catalogue_csv([sample()])
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    assert list(rows[0]) == list(EXPORT_COLUMNS)
    assert json.loads(rows[0]["specification_attributes"]) == {"flow": 50, "head": "30 m"}
    assert rows[0]["code"] == "MEC-001"
    assert rows[0]["approval_status"] == "Approved"


def test_export_empty_still_has_headers():
    raw = export_catalogue_csv([]).decode("utf-8-sig")
    assert raw.strip().splitlines()[0] == ",".join(EXPORT_COLUMNS)


def test_csv_escaping_and_unicode():
    item = sample()
    item.description = 'Pump, "Heavy" – 15 kW'
    rows = list(csv.DictReader(io.StringIO(export_catalogue_csv([item]).decode("utf-8-sig"))))
    assert rows[0]["description"] == item.description


def test_export_does_not_mutate_input():
    item = sample()
    before = dict(item.__dict__)
    export_catalogue_csv([item])
    assert item.__dict__ == before
