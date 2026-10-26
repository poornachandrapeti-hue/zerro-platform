"""Links from construction to records other modules already own.

A posted issue or reservation can be named on a daily line. That name does not
change the stores balance and is not the installed quantity. Planning dates stay
on the work package. Crew and equipment stay as text. Permit, inspection, and
quality-hold checks stay readiness notes.
"""

from decimal import Decimal

from fastapi import HTTPException

from app.domains.supply_chain.models import ProcurementItem, StockPosting, StockPostingLine

from .models import (
    ConstructionActivity,
    ProgressLine,
    ProgressReport,
    ReadinessCheck,
    WorkPackage,
)
from .service import day, qty

LINKABLE = {"Issue", "Reserve"}
STORES_NOTE = (
    "A posted issue or reservation can be named on a daily line. "
    "The stores balance stays unchanged. That quantity is not the installed quantity."
)
PLANNING_NOTE = "Planned dates are stored on the work package. No schedule baseline was created."
HR_NOTE = "Crew is written on the daily report. No attendance record was created."
EQUIPMENT_NOTE = "Equipment hours are written on the daily report. No equipment register was created."
HSE_NOTE = "A permit check is readiness evidence. No work permit was created."
ASSESSMENT_NOTE = "An approved risk assessment does not authorize work."
PERMIT_NOTE = "An expired, suspended, or not-yet-active permit blocks start and resume of the work it covers. Authorization is not activation."
FIELD_NOTE = (
    "A saved eligibility, toolbox, or finding rule can block the work it names. "
    "A crew line is not attendance. Closing a finding is not a safety-hold release."
)
INCIDENT_NOTE = "An incident report does not hold work and does not replace the emergency response."
HOLD_NOTE = (
    "An active safety hold blocks start and resume of the work it covers. "
    "Releasing a quality hold does not clear it. Releasing the safety hold does not start the work."
)
EMERGENCY_NOTE = (
    "An emergency record does not start the response and does not hold work. "
    "The approved communication procedure is named on the project. This application does not place the emergency call."
)
ENVIRONMENT_NOTE = (
    "An environmental record does not hold work and does not file a regulatory report. "
    "A reading is compared only with a criterion saved on the project."
)
QA_NOTE = (
    "Inspection and quality-hold checks are readiness evidence. "
    "No inspection result was created. Accepted quantity stays closed."
)
REFERENCE_NOTE = "This stores quantity is not the installed quantity."


def _assessments(db, project):
    from app.domains.hse.models import HseAssessment

    return [
        {"id": row.id, "number": row.number, "status": row.status}
        for row in db.query(HseAssessment).filter_by(project_id=project.id).order_by(HseAssessment.id.desc()).limit(20)
    ]


def linked_posting(db, project, posting_id):
    if posting_id is None:
        return None
    posting = db.get(StockPosting, posting_id)
    if (
        not posting
        or posting.project_id != project.id
        or posting.organization_id != project.organization_id
        or posting.status != "Posted"
        or posting.kind not in LINKABLE
    ):
        raise HTTPException(422, "Choose a posted issue or reservation on this project")
    return posting


def posting_reference(db, posting):
    if not posting:
        return None
    rows = []
    parts = []
    lines = (
        db.query(StockPostingLine)
        .filter_by(posting_id=posting.id)
        .order_by(StockPostingLine.id)
        .all()
    )
    for line in lines:
        item = db.get(ProcurementItem, line.item_id)
        amount = qty(line.quantity)
        parts.append(f"{amount} {line.unit}")
        rows.append(
            {
                "item_code": item.code if item else "",
                "item_name": item.description if item else "",
                "quantity": amount,
                "unit": line.unit,
            }
        )
    return {
        "id": posting.id,
        "number": posting.number,
        "kind": posting.kind,
        "status": posting.status,
        "quantity_label": ", ".join(parts),
        "lines": rows,
        "note": REFERENCE_NOTE,
    }


def _check_link(package, row, label=None):
    return {
        "id": row.id,
        "package_code": package.code,
        "check_type": row.check_type,
        "classification": row.classification,
        "status": row.status,
        "evidence": row.evidence,
        "source_label": label if label is not None else row.source_label,
    }


def board(db, project):
    postings = (
        db.query(StockPosting)
        .filter(
            StockPosting.project_id == project.id,
            StockPosting.status == "Posted",
            StockPosting.kind.in_(tuple(LINKABLE)),
        )
        .order_by(StockPosting.number)
        .all()
    )
    packages = (
        db.query(WorkPackage)
        .filter(WorkPackage.project_id == project.id, WorkPackage.status != "Cancelled")
        .order_by(WorkPackage.code)
        .all()
    )
    checks = []
    for package in packages:
        rows = (
            db.query(ReadinessCheck)
            .filter_by(package_id=package.id)
            .order_by(ReadinessCheck.check_type)
            .all()
        )
        for row in rows:
            label = None
            if row.check_type == "Material":
                from .readiness import material_gate

                _state, label, _sources = material_gate(db, project, package)
            checks.append(_check_link(package, row, label))

    def of_type(*names):
        return [row for row in checks if row["check_type"] in names]

    crew = []
    equipment = []
    reports = (
        db.query(ProgressReport)
        .filter(ProgressReport.project_id == project.id, ProgressReport.status != "Cancelled")
        .order_by(ProgressReport.report_date.desc(), ProgressReport.id.desc())
        .all()
    )
    for report in reports:
        lines = db.query(ProgressLine).filter_by(report_id=report.id).order_by(ProgressLine.id).all()
        for line in lines:
            activity = db.get(ConstructionActivity, line.activity_id)
            code = activity.code if activity else ""
            if line.crew_reference.strip():
                crew.append(
                    {
                        "report_number": report.number,
                        "activity_code": code,
                        "crew_reference": line.crew_reference,
                    }
                )
            if line.equipment_hours is not None:
                equipment.append(
                    {
                        "report_number": report.number,
                        "activity_code": code,
                        "equipment_hours": format(Decimal(line.equipment_hours).quantize(Decimal("0.01")), "f"),
                    }
                )
    return {
        "stores": {
            "note": STORES_NOTE,
            "postings": [posting_reference(db, row) for row in postings],
            "material_checks": of_type("Material"),
        },
        "planning": {
            "note": PLANNING_NOTE,
            "packages": [
                {
                    "id": package.id,
                    "code": package.code,
                    "name": package.name,
                    "status": package.status,
                    "planning_reference": package.planning_reference,
                    "planned_start": day(package.planned_start),
                    "planned_finish": day(package.planned_finish),
                }
                for package in packages
            ],
        },
        "hr": {"note": HR_NOTE, "checks": of_type("Manpower"), "crew": crew},
        "equipment": {"note": EQUIPMENT_NOTE, "entries": equipment},
        "hse": {
            "note": HSE_NOTE,
            "assessment_note": ASSESSMENT_NOTE,
            "permit_note": PERMIT_NOTE,
            "field_note": FIELD_NOTE,
            "incident_note": INCIDENT_NOTE,
            "hold_note": HOLD_NOTE,
            "emergency_note": EMERGENCY_NOTE,
            "environment_note": ENVIRONMENT_NOTE,
            "checks": of_type("Permit"),
            "assessments": _assessments(db, project),
        },
        "qa": {"note": QA_NOTE, "checks": of_type("Inspection", "Quality hold"), "accepted": "not open"},
    }
