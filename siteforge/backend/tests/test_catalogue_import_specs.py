from app.domains.supply_chain.service import _import_specification_attributes, ItemInPayload


def test_import_json_specification_attributes():
    header = ["code", "specification_attributes"]
    row = ["P-1", '{"flow_m3_hr": 60, "seal_type": "mech"}']
    attrs, error = _import_specification_attributes(header, row)
    assert error == ""
    assert attrs == {"flow_m3_hr": 60, "seal_type": "mech"}


def test_import_spec_dot_columns():
    header = ["code", "spec.grade", "spec.diameter_mm", "spec.coated"]
    row = ["R-1", "Fe500", "16", "true"]
    attrs, error = _import_specification_attributes(header, row)
    assert error == ""
    assert attrs == {"grade": "Fe500", "diameter_mm": 16, "coated": True}


def test_import_invalid_json_reported():
    header = ["specification_attributes"]
    row = ["{bad"]
    attrs, error = _import_specification_attributes(header, row)
    assert attrs == {}
    assert "JSON" in error


def test_item_in_payload_carries_structured_fields():
    payload = ItemInPayload(
        {
            "code": "C-1",
            "description": "Concrete",
            "item_type": "Material",
            "category": "Concrete",
            "subcategory": "Ready Mix",
            "discipline_ids": [1],
            "specification": "M30",
            "size_rating": "",
            "material_grade": "M30",
            "applicable_standard": "IS 456",
            "base_unit": "m3",
            "approved_make": "",
            "model_number": "",
            "manufacturer_part_number": "",
            "hsn_code": "6810",
            "inspection_required": True,
            "tracking_required": False,
            "mtc_required": True,
            "calibration_certificate_required": False,
            "shelf_life_applicable": False,
            "shelf_life_days": None,
            "specification_discipline": "Civil",
            "specification_attributes": {"grade": "M30"},
        }
    )
    assert payload.subcategory == "Ready Mix"
    assert payload.specification_attributes == {"grade": "M30"}
    assert payload.mtc_required is True
    assert payload.item_type == "Material"
