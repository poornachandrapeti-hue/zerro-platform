"""Catalogue matching helpers for Engineering MTO and related consumers."""
from __future__ import annotations


def _norm(value) -> str:
    return " ".join(str(value or "").casefold().split())


def _contains(haystack: str, needle: str) -> bool:
    return bool(needle) and needle in haystack


def score_item_match(line, item) -> dict:
    """Score technical compatibility between an MTO line and a catalogue item.

    Returns score 0..100 and human-readable reasons. Does not write data.
    """
    if item is None:
        return {"score": 0, "compatible": False, "reasons": ["Catalogue item missing"]}

    score = 0
    reasons = []
    line_text = " ".join(
        [
            _norm(getattr(line, "description", "")),
            _norm(getattr(line, "specification", "")),
            _norm(getattr(line, "reference", "")),
        ]
    )
    item_text = " ".join(
        [
            _norm(item.code),
            _norm(item.description),
            _norm(getattr(item, "specification", "")),
            _norm(getattr(item, "material_grade", "")),
            _norm(getattr(item, "size_rating", "")),
            _norm(getattr(item, "category", "")),
            " ".join(f"{k} {v}" for k, v in (getattr(item, "specification_attributes", None) or {}).items()),
        ]
    )

    if _norm(getattr(line, "description", "")) and _norm(line.description) in item_text:
        score += 35
        reasons.append("Description overlaps catalogue identity")
    elif any(token and token in item_text for token in _norm(getattr(line, "description", "")).split() if len(token) > 3):
        score += 15
        reasons.append("Partial description token match")

    line_spec = _norm(getattr(line, "specification", ""))
    if line_spec:
        if _contains(item_text, line_spec):
            score += 30
            reasons.append("Specification/grade matches catalogue")
        else:
            reasons.append("Specification/grade not found on catalogue item")
            score -= 20

    line_unit = _norm(getattr(line, "unit", ""))
    item_unit = _norm(getattr(item, "base_unit", ""))
    if line_unit and item_unit:
        if line_unit == item_unit:
            score += 25
            reasons.append("UOM matches")
        else:
            reasons.append(f"UOM differs ({getattr(line, 'unit', '')} vs {item.base_unit})")

    if getattr(item, "active", False) and getattr(item, "approval_status", "") == "Approved":
        score += 10
        reasons.append("Approved active catalogue item")
    else:
        reasons.append("Catalogue item is not approved and active")
        score -= 40

    score = max(0, min(100, score))
    compatible = score >= 50 and getattr(item, "approval_status", "") == "Approved" and getattr(item, "active", False)
    return {"score": score, "compatible": compatible, "reasons": reasons}


def compatibility_flags(line, item, has_conversion: bool = False) -> list[str]:
    result = score_item_match(line, item)
    flags = []
    if not result["compatible"]:
        flags.append("Catalogue match is weak or incompatible")
    line_unit = _norm(getattr(line, "unit", ""))
    item_unit = _norm(getattr(item, "base_unit", "")) if item else ""
    if line_unit and item_unit and line_unit != item_unit and not has_conversion:
        flags.append(f"Unit {getattr(line, 'unit', '')} differs from catalogue unit {item.base_unit} and has no conversion")
    line_spec = _norm(getattr(line, "specification", ""))
    if line_spec and item:
        item_blob = " ".join(
            [
                _norm(getattr(item, "specification", "")),
                _norm(getattr(item, "material_grade", "")),
                _norm(getattr(item, "size_rating", "")),
                " ".join(str(v) for v in (getattr(item, "specification_attributes", None) or {}).values()),
            ]
        )
        if not _contains(item_blob, line_spec):
            flags.append("Line specification does not match catalogue grade/size/specification")
    return flags
