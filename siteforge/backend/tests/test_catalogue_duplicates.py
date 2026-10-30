from types import SimpleNamespace
from app.domains.supply_chain.catalogue_duplicates import (
    classify_match,
    normalize_mpn,
    summarize_duplicates,
    technical_fingerprint,
)


def test_normalize_mpn_strips_noise():
    assert normalize_mpn(" AB-12 / 34 ") == "ab1234"


def test_exact_mpn_match_is_blocking():
    candidate = SimpleNamespace(
        category="Pumps",
        subcategory="",
        description="Other",
        material_grade="",
        manufacturer_part_number="AB-123",
        size_rating="",
        specification_attributes={},
    )
    assert classify_match(
        candidate,
        mpn=normalize_mpn("AB123"),
        fingerprint="x",
        description_key="pump",
        category="Pumps",
    ) == "exact"


def test_same_technical_fingerprint_is_exact():
    attrs = {"flow_m3_hr": "60", "head_m": "30"}
    fingerprint = technical_fingerprint(
        category="Pumps",
        subcategory="Centrifugal",
        description="Process pump",
        material_grade="SS316",
        manufacturer_part_number="",
        size_rating="80NB",
        specification_attributes=attrs,
    )
    candidate = SimpleNamespace(
        category="Pumps",
        subcategory="Centrifugal",
        description="Process pump",
        material_grade="SS316",
        manufacturer_part_number="",
        size_rating="80NB",
        specification_attributes=attrs,
    )
    assert classify_match(
        candidate,
        mpn="",
        fingerprint=fingerprint,
        description_key="process pump",
        category="Pumps",
    ) == "exact"


def test_same_category_description_is_possible_only():
    candidate = SimpleNamespace(
        category="Pumps",
        subcategory="Other",
        description="Process Pump",
        material_grade="CS",
        manufacturer_part_number="",
        size_rating="",
        specification_attributes={},
    )
    assert classify_match(
        candidate,
        mpn="",
        fingerprint="different",
        description_key="process pump",
        category="Pumps",
    ) == "possible"


def test_summarize_marks_exact_as_blocking():
    summary = summarize_duplicates(
        [
            {"code": "A", "match_type": "possible"},
            {"code": "B", "match_type": "exact"},
        ]
    )
    assert summary["blocking"] is True
    assert [row["code"] for row in summary["exact"]] == ["B"]
