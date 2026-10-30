from types import SimpleNamespace
from app.domains.supply_chain.catalogue_match import score_item_match, compatibility_flags


def test_weak_spec_mismatch_is_flagged():
    line = SimpleNamespace(description="Concrete", specification="M40", unit="m3", reference="")
    item = SimpleNamespace(
        code="CON-M30",
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
    result = score_item_match(line, item)
    assert result["score"] < 80
    flags = compatibility_flags(line, item, has_conversion=True)
    assert any("specification" in flag.casefold() for flag in flags)


def test_strong_match_is_compatible():
    line = SimpleNamespace(description="Reinforcement Steel Fe500", specification="Fe500", unit="kg", reference="")
    item = SimpleNamespace(
        code="REBAR-500",
        description="Reinforcement Steel",
        specification="",
        material_grade="Fe500",
        size_rating="16mm",
        category="Reinforcement",
        specification_attributes={"steel_grade": "Fe500"},
        base_unit="kg",
        active=True,
        approval_status="Approved",
    )
    result = score_item_match(line, item)
    assert result["compatible"] is True
    assert result["score"] >= 50
