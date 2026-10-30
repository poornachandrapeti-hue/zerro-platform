"""Organization catalogue reference masters. Soft-enforced when populated."""
from __future__ import annotations

from fastapi import HTTPException

from .models import (
    CatalogueCategory,
    CatalogueManufacturer,
    CatalogueMaterialGrade,
    CatalogueStandard,
    CatalogueSubcategory,
    CatalogueUom,
)
from .specification_templates import TEMPLATES


def _key(value: str) -> str:
    return value.strip().casefold()


ALLOWED_QA_DOC_TYPES = {
    "MTC",
    "Inspection Report",
    "Calibration Certificate",
    "CoC",
    "Material Certificate",
    "Test Certificate",
    "Datasheet",
}


def normalize_qa_document_types(values) -> list[str]:
    if values in (None, ""):
        return []
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",") if part.strip()]
    if not isinstance(values, list):
        raise HTTPException(422, "qa_document_types must be a list")
    cleaned = []
    for value in values:
        if not isinstance(value, str) or not (1 <= len(value.strip()) <= 80):
            raise HTTPException(422, "Invalid QA document type")
        name = value.strip()
        if name not in ALLOWED_QA_DOC_TYPES:
            raise HTTPException(422, f"Unsupported QA document type: {name}")
        if name not in cleaned:
            cleaned.append(name)
    if len(cleaned) > 20:
        raise HTTPException(422, "Too many QA document types")
    return cleaned


def category_payload(row, subcategories=None):
    return {
        "id": row.id,
        "discipline": row.discipline,
        "name": row.name,
        "active": row.active,
        "qa_document_types": list(getattr(row, "qa_document_types", None) or []),
        "subcategories": subcategories or [],
    }


def subcategory_payload(row):
    return {"id": row.id, "category_id": row.category_id, "name": row.name, "active": row.active}


def uom_payload(row):
    return {"id": row.id, "code": row.code, "name": row.name, "active": row.active}


def grade_payload(row):
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "discipline": row.discipline,
        "active": row.active,
    }


def standard_payload(row):
    return {"id": row.id, "code": row.code, "title": row.title, "active": row.active}


def manufacturer_payload(row):
    return {"id": row.id, "code": row.code, "name": row.name, "active": row.active}


def list_categories(db, organization_id, discipline: str | None = None, include_inactive=False):
    query = db.query(CatalogueCategory).filter_by(organization_id=organization_id)
    if discipline:
        query = query.filter_by(discipline=discipline)
    if not include_inactive:
        query = query.filter_by(active=True)
    rows = query.order_by(CatalogueCategory.discipline, CatalogueCategory.name).all()
    subs = (
        db.query(CatalogueSubcategory)
        .filter_by(organization_id=organization_id)
        .order_by(CatalogueSubcategory.name)
        .all()
    )
    by_cat = {}
    for sub in subs:
        if include_inactive or sub.active:
            by_cat.setdefault(sub.category_id, []).append(subcategory_payload(sub))
    return [category_payload(row, by_cat.get(row.id, [])) for row in rows]


def save_category(db, user, *, discipline: str, name: str, active=True, qa_document_types=None, row=None):
    discipline = discipline.strip()
    name = name.strip()
    if not (1 <= len(discipline) <= 100 and 1 <= len(name) <= 120):
        raise HTTPException(422, "Enter a valid discipline and category name")
    name_key = _key(name)
    existing = (
        db.query(CatalogueCategory)
        .filter_by(organization_id=user.organization_id, discipline=discipline, name_key=name_key)
        .first()
    )
    if existing and (row is None or existing.id != row.id):
        raise HTTPException(409, "Category already exists for this discipline")
    docs = normalize_qa_document_types(
        qa_document_types if qa_document_types is not None else getattr(row, "qa_document_types", []) if row else []
    )
    if row is None:
        row = CatalogueCategory(
            organization_id=user.organization_id,
            discipline=discipline,
            name=name,
            name_key=name_key,
            qa_document_types=docs,
            modified_by=user.id,
        )
        db.add(row)
    else:
        row.discipline = discipline
        row.name = name
        row.name_key = name_key
        row.qa_document_types = docs
        row.modified_by = user.id
    row.active = bool(active)
    db.flush()
    return row


def qa_documents_for_item(db, organization_id: int, discipline: str, category: str) -> list[str]:
    row = (
        db.query(CatalogueCategory)
        .filter_by(organization_id=organization_id, discipline=discipline, name_key=_key(category), active=True)
        .first()
    )
    return list(getattr(row, "qa_document_types", None) or []) if row else []


def save_subcategory(db, user, *, category_id: int, name: str, active=True, row=None):
    category = db.get(CatalogueCategory, category_id)
    if not category or category.organization_id != user.organization_id:
        raise HTTPException(404, "Category not found")
    name = name.strip()
    if not (1 <= len(name) <= 120):
        raise HTTPException(422, "Enter a valid subcategory name")
    name_key = _key(name)
    existing = (
        db.query(CatalogueSubcategory)
        .filter_by(organization_id=user.organization_id, category_id=category_id, name_key=name_key)
        .first()
    )
    if existing and (row is None or existing.id != row.id):
        raise HTTPException(409, "Subcategory already exists for this category")
    if row is None:
        row = CatalogueSubcategory(
            organization_id=user.organization_id,
            category_id=category_id,
            name=name,
            name_key=name_key,
            modified_by=user.id,
        )
        db.add(row)
    else:
        if row.organization_id != user.organization_id:
            raise HTTPException(404, "Subcategory not found")
        row.category_id = category_id
        row.name = name
        row.name_key = name_key
        row.modified_by = user.id
    row.active = bool(active)
    db.flush()
    return row


def save_uom(db, user, *, code: str, name: str = "", active=True, row=None):
    code = code.strip()
    if not (1 <= len(code) <= 20):
        raise HTTPException(422, "Enter a valid UOM code")
    code_key = _key(code)
    existing = db.query(CatalogueUom).filter_by(organization_id=user.organization_id, code_key=code_key).first()
    if existing and (row is None or existing.id != row.id):
        raise HTTPException(409, "UOM already exists")
    if row is None:
        row = CatalogueUom(
            organization_id=user.organization_id,
            code=code,
            code_key=code_key,
            name=(name or code).strip()[:80],
            modified_by=user.id,
        )
        db.add(row)
    else:
        row.code = code
        row.code_key = code_key
        row.name = (name or code).strip()[:80]
        row.modified_by = user.id
    row.active = bool(active)
    db.flush()
    return row


def save_grade(db, user, *, code: str, name: str = "", discipline: str = "", active=True, row=None):
    code = code.strip()
    if not (1 <= len(code) <= 80):
        raise HTTPException(422, "Enter a valid material grade code")
    code_key = _key(code)
    existing = (
        db.query(CatalogueMaterialGrade)
        .filter_by(organization_id=user.organization_id, code_key=code_key)
        .first()
    )
    if existing and (row is None or existing.id != row.id):
        raise HTTPException(409, "Material grade already exists")
    if row is None:
        row = CatalogueMaterialGrade(
            organization_id=user.organization_id,
            code=code,
            code_key=code_key,
            name=(name or code).strip()[:120],
            discipline=(discipline or "").strip()[:100],
            modified_by=user.id,
        )
        db.add(row)
    else:
        row.code = code
        row.code_key = code_key
        row.name = (name or code).strip()[:120]
        row.discipline = (discipline or "").strip()[:100]
        row.modified_by = user.id
    row.active = bool(active)
    db.flush()
    return row


def save_standard(db, user, *, code: str, title: str = "", active=True, row=None):
    code = code.strip()
    if not (1 <= len(code) <= 80):
        raise HTTPException(422, "Enter a valid standard code")
    code_key = _key(code)
    existing = db.query(CatalogueStandard).filter_by(organization_id=user.organization_id, code_key=code_key).first()
    if existing and (row is None or existing.id != row.id):
        raise HTTPException(409, "Standard already exists")
    if row is None:
        row = CatalogueStandard(
            organization_id=user.organization_id,
            code=code,
            code_key=code_key,
            title=(title or code).strip()[:200],
            modified_by=user.id,
        )
        db.add(row)
    else:
        row.code = code
        row.code_key = code_key
        row.title = (title or code).strip()[:200]
        row.modified_by = user.id
    row.active = bool(active)
    db.flush()
    return row


def save_manufacturer(db, user, *, code: str, name: str, active=True, row=None):
    code = code.strip()
    name = name.strip()
    if not (1 <= len(code) <= 80 and 1 <= len(name) <= 200):
        raise HTTPException(422, "Enter a valid manufacturer code and name")
    code_key = _key(code)
    existing = (
        db.query(CatalogueManufacturer)
        .filter_by(organization_id=user.organization_id, code_key=code_key)
        .first()
    )
    if existing and (row is None or existing.id != row.id):
        raise HTTPException(409, "Manufacturer already exists")
    if row is None:
        row = CatalogueManufacturer(
            organization_id=user.organization_id,
            code=code,
            code_key=code_key,
            name=name,
            modified_by=user.id,
        )
        db.add(row)
    else:
        row.code = code
        row.code_key = code_key
        row.name = name
        row.modified_by = user.id
    row.active = bool(active)
    db.flush()
    return row


def seed_categories_from_templates(db, user):
    created = 0
    for discipline, categories in TEMPLATES.items():
        for category_name in categories:
            existing = (
                db.query(CatalogueCategory)
                .filter_by(
                    organization_id=user.organization_id,
                    discipline=discipline,
                    name_key=_key(category_name),
                )
                .first()
            )
            if existing:
                if not existing.active:
                    existing.active = True
                    existing.modified_by = user.id
                    created += 1
                continue
            db.add(
                CatalogueCategory(
                    organization_id=user.organization_id,
                    discipline=discipline,
                    name=category_name,
                    name_key=_key(category_name),
                    modified_by=user.id,
                )
            )
            created += 1
    db.flush()
    return created


def _allowed_list(names, limit=12):
    values = sorted({str(name) for name in names if name})
    if not values:
        return "(none)"
    shown = ", ".join(values[:limit])
    if len(values) > limit:
        shown += f" (+{len(values) - limit} more)"
    return shown


def enforce_item_masters(db, user, data, discipline_name: str):
    """When masters are configured, require item values to match active entries."""
    categories = (
        db.query(CatalogueCategory)
        .filter_by(organization_id=user.organization_id, discipline=discipline_name, active=True)
        .all()
    )
    if not categories:
        # Fall back to any active org category for this discipline name_key (spacing/case variants).
        categories = [
            row
            for row in db.query(CatalogueCategory)
            .filter_by(organization_id=user.organization_id, active=True)
            .all()
            if _key(row.discipline) == _key(discipline_name)
        ]
    if categories:
        match = next((row for row in categories if row.name_key == _key(data.category)), None)
        if match is None:
            raise HTTPException(
                422,
                f"Category '{data.category}' is not in the {discipline_name} master. "
                f"Allowed: {_allowed_list(row.name for row in categories)}",
            )
        sub_name = (getattr(data, "subcategory", "") or "").strip()
        subs = (
            db.query(CatalogueSubcategory)
            .filter_by(organization_id=user.organization_id, category_id=match.id, active=True)
            .all()
        )
        if subs and sub_name and not any(sub.name_key == _key(sub_name) for sub in subs):
            raise HTTPException(
                422,
                f"Subcategory '{sub_name}' is not in the {match.name} master. "
                f"Allowed: {_allowed_list(sub.name for sub in subs)}",
            )
        if subs and not sub_name:
            raise HTTPException(
                422,
                f"Select a subcategory for {match.name}. Allowed: {_allowed_list(sub.name for sub in subs)}",
            )

    uoms = db.query(CatalogueUom).filter_by(organization_id=user.organization_id, active=True).all()
    if uoms and not any(row.code_key == _key(data.base_unit) for row in uoms):
        raise HTTPException(
            422,
            f"UOM '{data.base_unit}' is not in the UOM master. Allowed: {_allowed_list(row.code for row in uoms)}",
        )
    for label, value in (
        ("Purchase UOM", getattr(data, "purchase_unit", "") or ""),
        ("Issue UOM", getattr(data, "issue_unit", "") or ""),
    ):
        unit = value.strip()
        if not unit:
            continue
        if uoms and not any(row.code_key == _key(unit) for row in uoms):
            raise HTTPException(
                422,
                f"{label} '{unit}' is not in the UOM master. Allowed: {_allowed_list(row.code for row in uoms)}",
            )

    grade = (getattr(data, "material_grade", "") or "").strip()
    grades = db.query(CatalogueMaterialGrade).filter_by(organization_id=user.organization_id, active=True).all()
    if grade and grades and not any(row.code_key == _key(grade) for row in grades):
        raise HTTPException(
            422,
            f"Material grade '{grade}' is not in the grade master. Allowed: {_allowed_list(row.code for row in grades)}",
        )

    standard = (getattr(data, "applicable_standard", "") or "").strip()
    standards = db.query(CatalogueStandard).filter_by(organization_id=user.organization_id, active=True).all()
    if standard and standards and not any(row.code_key == _key(standard) for row in standards):
        raise HTTPException(
            422,
            f"Standard '{standard}' is not in the standards master. Allowed: {_allowed_list(row.code for row in standards)}",
        )

    make = (getattr(data, "approved_make", "") or "").strip()
    manufacturers = (
        db.query(CatalogueManufacturer).filter_by(organization_id=user.organization_id, active=True).all()
    )
    if make and manufacturers and not any(
        row.code_key == _key(make) or _key(row.name) == _key(make) for row in manufacturers
    ):
        raise HTTPException(
            422,
            f"Manufacturer '{make}' is not in the manufacturer master. "
            f"Allowed: {_allowed_list([row.code or row.name for row in manufacturers])}",
        )
