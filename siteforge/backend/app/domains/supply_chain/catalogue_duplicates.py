"""Catalogue duplicate detection helpers. Code uniqueness remains DB-enforced."""
from __future__ import annotations


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").casefold().split())


def normalize_mpn(value: str | None) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def technical_fingerprint(
    *,
    category: str,
    subcategory: str = "",
    description: str = "",
    material_grade: str = "",
    manufacturer_part_number: str = "",
    size_rating: str = "",
    specification_attributes: dict | None = None,
) -> str:
    attrs = specification_attributes or {}
    attr_part = "|".join(f"{key}={normalize_text(str(attrs[key]))}" for key in sorted(attrs))
    return "|".join(
        [
            normalize_text(category),
            normalize_text(subcategory),
            normalize_text(description),
            normalize_text(material_grade),
            normalize_mpn(manufacturer_part_number),
            normalize_text(size_rating),
            attr_part,
        ]
    )


def classify_match(candidate, *, mpn: str, fingerprint: str, description_key: str, category: str) -> str | None:
    """Return 'exact', 'possible', or None."""
    candidate_mpn = normalize_mpn(getattr(candidate, "manufacturer_part_number", ""))
    if mpn and candidate_mpn and mpn == candidate_mpn:
        return "exact"
    candidate_fp = technical_fingerprint(
        category=getattr(candidate, "category", ""),
        subcategory=getattr(candidate, "subcategory", ""),
        description=getattr(candidate, "description", ""),
        material_grade=getattr(candidate, "material_grade", ""),
        manufacturer_part_number=getattr(candidate, "manufacturer_part_number", ""),
        size_rating=getattr(candidate, "size_rating", ""),
        specification_attributes=getattr(candidate, "specification_attributes", None) or {},
    )
    if fingerprint and candidate_fp == fingerprint:
        return "exact"
    if (
        description_key
        and normalize_text(getattr(candidate, "category", "")) == normalize_text(category)
        and normalize_text(getattr(candidate, "description", "")) == description_key
    ):
        return "possible"
    return None


def summarize_duplicates(matches: list[dict]) -> dict:
    exact = [row for row in matches if row.get("match_type") == "exact"]
    possible = [row for row in matches if row.get("match_type") == "possible"]
    return {
        "blocking": bool(exact),
        "exact": exact,
        "possible": possible,
        "matches": matches,
    }
