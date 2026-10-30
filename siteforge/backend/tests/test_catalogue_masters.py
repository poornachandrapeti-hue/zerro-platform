from types import SimpleNamespace
from fastapi import HTTPException
import pytest
from app.domains.supply_chain.catalogue_masters import enforce_item_masters, _key
from app.domains.supply_chain.catalogue_match import score_item_match, compatibility_flags


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter_by(self, **kwargs):
        filtered = []
        for row in self.rows:
            if all(getattr(row, key, None) == value for key, value in kwargs.items()):
                filtered.append(row)
        return FakeQuery(filtered)

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class FakeDB:
    def __init__(self, rows_by_model):
        self.rows_by_model = rows_by_model

    def query(self, model):
        return FakeQuery(self.rows_by_model.get(model, []))


def test_key_normalizes():
    assert _key("  Nos ") == "nos"


def test_enforce_requires_category_when_master_exists():
    from app.domains.supply_chain.models import CatalogueCategory, CatalogueUom

    category = SimpleNamespace(
        organization_id=1, discipline="Civil", name="Concrete", name_key="concrete", id=9, active=True
    )
    db = FakeDB({CatalogueCategory: [category], CatalogueUom: []})
    user = SimpleNamespace(organization_id=1)
    data = SimpleNamespace(category="Unknown", subcategory="", base_unit="m3", material_grade="", applicable_standard="", approved_make="")
    with pytest.raises(HTTPException) as exc:
        enforce_item_masters(db, user, data, "Civil")
    assert exc.value.status_code == 422
    assert "Concrete" in str(exc.value.detail)
    assert "Unknown" in str(exc.value.detail)


def test_enforce_allows_when_masters_empty():
    from app.domains.supply_chain.models import (
        CatalogueCategory,
        CatalogueManufacturer,
        CatalogueMaterialGrade,
        CatalogueStandard,
        CatalogueUom,
    )

    db = FakeDB({
        CatalogueCategory: [],
        CatalogueUom: [],
        CatalogueMaterialGrade: [],
        CatalogueStandard: [],
        CatalogueManufacturer: [],
    })
    user = SimpleNamespace(organization_id=1)
    data = SimpleNamespace(category="Anything", subcategory="", base_unit="kg", material_grade="Fe500", applicable_standard="", approved_make="")
    enforce_item_masters(db, user, data, "Civil")


def test_match_scores_grade_and_unit():
    line = SimpleNamespace(description="Reinforcement Steel Fe500", specification="Fe500", unit="kg", reference="")
    item = SimpleNamespace(
        code="REBAR-01",
        description="Reinforcement Steel",
        specification="",
        material_grade="Fe500",
        size_rating="16mm",
        category="Reinforcement",
        specification_attributes={},
        base_unit="kg",
        active=True,
        approval_status="Approved",
    )
    result = score_item_match(line, item)
    assert result["compatible"] is True
    assert result["score"] >= 50


def test_compatibility_flags_for_spec_mismatch():
    line = SimpleNamespace(description="Concrete", specification="M40", unit="m3")
    item = SimpleNamespace(
        code="CON-01",
        description="Ready Mix Concrete",
        specification="M30",
        material_grade="M30",
        size_rating="",
        category="Concrete",
        specification_attributes={},
        base_unit="m3",
        active=True,
        approval_status="Approved",
    )
    flags = compatibility_flags(line, item, has_conversion=True)
    assert any("specification" in flag.casefold() for flag in flags)


def test_enforce_rejects_unknown_purchase_uom():
    from app.domains.supply_chain.models import CatalogueCategory, CatalogueUom

    uom = SimpleNamespace(organization_id=1, code="kg", code_key="kg", active=True)
    db = FakeDB({CatalogueCategory: [], CatalogueUom: [uom]})
    user = SimpleNamespace(organization_id=1)
    data = SimpleNamespace(
        category="",
        subcategory="",
        base_unit="kg",
        purchase_unit="bag",
        issue_unit="kg",
        material_grade="",
        applicable_standard="",
        approved_make="",
    )
    with pytest.raises(HTTPException) as exc:
        enforce_item_masters(db, user, data, "Civil")
    assert exc.value.status_code == 422
    assert "Purchase UOM" in str(exc.value.detail)


def test_normalize_qa_document_types_allows_known_pack():
    from app.domains.supply_chain.catalogue_masters import normalize_qa_document_types

    assert normalize_qa_document_types(["MTC", "CoC", "MTC"]) == ["MTC", "CoC"]


def test_normalize_qa_document_types_rejects_unknown():
    from app.domains.supply_chain.catalogue_masters import normalize_qa_document_types

    with pytest.raises(HTTPException) as exc:
        normalize_qa_document_types(["Unknown Pack"])
    assert exc.value.status_code == 422
