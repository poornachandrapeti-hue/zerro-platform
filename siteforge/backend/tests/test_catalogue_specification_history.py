from types import SimpleNamespace
from copy import deepcopy
from app.domains.supply_chain.catalogue_specification_history import item_snapshot, history_payload
from app.domains.supply_chain.models import CatalogueItemSpecificationHistory


def make_item(**overrides):
    data = dict(code="MEC-001", description="Pump", item_type="Equipment",
        category="Pumps", discipline_ids=[1], specification="Rated pump",
        specification_attributes={"flow": 50}, size_rating="", base_unit="Nos",
        approved_make="", inspection_required=True, tracking_required=False,
        active=True, approval_status="Approved")
    data.update(overrides)
    return SimpleNamespace(**data)


def test_snapshot_includes_approval_and_specs():
    snap = item_snapshot(make_item())
    assert snap["approval_status"] == "Approved"
    assert snap["specification_attributes"]["flow"] == 50
    assert snap["base_unit"] == "Nos"


def test_snapshot_is_not_aliased_to_item():
    item = make_item(specification_attributes={"layers": [1, 2]})
    snap = item_snapshot(item)
    item.specification_attributes["layers"].append(3)
    assert snap["specification_attributes"]["layers"] == [1, 2]


def test_history_response_is_not_aliased():
    row = SimpleNamespace(sequence=1, item_version=2, event="Approve", reason="Valid",
        snapshot={"attributes": {"grade": "M30"}}, actor_id=9, created_at=None)
    p = history_payload(row)
    p["snapshot"]["attributes"]["grade"] = "M35"
    assert row.snapshot["attributes"]["grade"] == "M30"


def test_history_has_uniqueness_constraint():
    assert any("sequence" in tuple(c.name for c in constraint.columns)
        for constraint in CatalogueItemSpecificationHistory.__table__.constraints
        if hasattr(constraint, "columns"))


def test_history_is_organization_scoped():
    from pathlib import Path
    router = Path(__file__).resolve().parents[1] / "app/domains/supply_chain/router.py"
    source = router.read_text()
    assert '"/procurement/items/{item_id}/specification-history"' in source
    assert 'organization_id=u.organization_id, item_id=item_id' in source
