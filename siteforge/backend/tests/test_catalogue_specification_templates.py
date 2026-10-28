from fastapi import HTTPException
import pytest
from app.domains.supply_chain.specification_templates import TEMPLATES, list_templates, validate_attributes

@pytest.mark.parametrize("discipline,category", [(d,c) for d, group in TEMPLATES.items() for c in group])
def test_template_accepts_fields(discipline,category):
    key = TEMPLATES[discipline][category][0]
    assert validate_attributes(discipline,category,{key:"example"}) == {key:"example"}

def test_unrecognized_attributes_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_attributes("Mechanical","Pumps",{"unauthorized":"x"})
    assert exc.value.status_code == 422

def test_templates_nonempty():
    assert len(list_templates()) >= 6


def test_extended_disciplines_have_templates():
    assert "Roads & Buildings" in TEMPLATES
    assert "Telecom / ELV" in TEMPLATES
    assert "Ducting" in TEMPLATES["HVAC"]
    assert "Gaskets" in TEMPLATES["Piping"]


def test_extended_template_rejects_unknown_field():
    with pytest.raises(HTTPException) as exc:
        validate_attributes("Telecom / ELV", "CCTV", {"fabricated_field": "unexpected"})
    assert exc.value.status_code == 422
