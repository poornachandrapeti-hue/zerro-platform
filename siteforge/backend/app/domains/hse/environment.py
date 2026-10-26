"""Environmental records.

Waste inspections, spills, dust and noise, discharge checks, and monitoring
evidence are records. A reading is judged only against a criterion saved on
the project. The record does not hold work and does not file a report.
"""

from fastapi import HTTPException

from .models import (
    ENVIRONMENT_KINDS,
    ENVIRONMENT_RESULTS,
    HseAction,
    HseEnvironmentCriterion,
    HseEnvironmentRecord,
)
from .service import _area, _package, _tell, _watchers

ENVIRONMENT_NOTE = (
    "This record does not hold work and does not file a regulatory report. "
    "A reading is compared only with a criterion saved on this project. Sensor feeds are not connected."
)
ACTION_LINK_NOTE = "Linking an action does not close it and does not open a new one. Open Actions to record one."


def _key(value):
    return value.strip().casefold()


def add_criterion(db, user, project, data):
    kind = data.kind.strip()
    if kind and kind not in ENVIRONMENT_KINDS:
        raise HTTPException(422, "Choose an environmental record kind")
    key = _key(data.name)
    if db.query(HseEnvironmentCriterion).filter_by(project_id=project.id, name_key=key).first():
        raise HTTPException(409, "That criterion already exists")
    row = HseEnvironmentCriterion(
        organization_id=project.organization_id,
        project_id=project.id,
        name=data.name.strip(),
        name_key=key,
        kind=kind,
        threshold=data.threshold.strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _criterion(db, project, criterion_id, kind):
    if not criterion_id:
        return None
    row = db.get(HseEnvironmentCriterion, criterion_id)
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Choose a criterion saved on this project")
    if row.kind and row.kind != kind:
        raise HTTPException(422, "That criterion is for a different record")
    return row


def _action(db, project, action_id):
    if not action_id:
        return None
    row = db.get(HseAction, action_id)
    if not row or row.project_id != project.id:
        raise HTTPException(422, "Choose an action on this project")
    return row


def add_record(db, user, project, data):
    if data.kind not in ENVIRONMENT_KINDS:
        raise HTTPException(422, "Choose an environmental record kind")
    if data.result not in ENVIRONMENT_RESULTS:
        raise HTTPException(422, "Choose a result")
    if data.kind == "Monitoring evidence" and len(data.evidence.strip()) < 3:
        raise HTTPException(422, "Record the monitoring evidence")
    if data.result != "Not assessed":
        if not data.criterion_id:
            raise HTTPException(422, "Save the project criterion before comparing a reading")
        if len(data.reading.strip()) < 3:
            raise HTTPException(422, "Write the reading")
    _area(db, project, data.area_id)
    package = _package(db, project, data.package_id)
    criterion = _criterion(db, project, data.criterion_id, data.kind)
    action = _action(db, project, data.action_id)
    key = _key(data.number)
    if db.query(HseEnvironmentRecord).filter_by(project_id=project.id, number_key=key).first():
        raise HTTPException(409, "That environmental record number already exists")
    row = HseEnvironmentRecord(
        organization_id=project.organization_id,
        project_id=project.id,
        number=data.number.strip(),
        number_key=key,
        kind=data.kind,
        description=data.description.strip(),
        recorded_on=data.recorded_on,
        area_id=data.area_id,
        package_id=package.id if package else None,
        criterion_id=criterion.id if criterion else None,
        reading=data.reading.strip(),
        result=data.result,
        evidence=data.evidence.strip(),
        action_id=action.id if action else None,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    if row.result == "Outside criteria":
        _tell(
            db,
            project,
            _watchers(db, project),
            "An environmental reading is outside the saved criterion",
            f"{row.number} is outside the saved project criterion. This notice does not hold work and does not file a report.",
            f"hse.environment.{row.id}",
        )
    return row


def record_view(db, project, row):
    criterion = db.get(HseEnvironmentCriterion, row.criterion_id) if row.criterion_id else None
    action = db.get(HseAction, row.action_id) if row.action_id else None
    package_status = ""
    if row.package_id:
        package = _package(db, project, row.package_id)
        package_status = package.status if package else ""
    return {
        "id": row.id,
        "number": row.number,
        "kind": row.kind,
        "description": row.description,
        "recorded_on": row.recorded_on.isoformat(),
        "reading": row.reading,
        "result": row.result,
        "evidence": row.evidence,
        "criterion_name": criterion.name if criterion else "",
        "threshold": criterion.threshold if criterion else "",
        "action_id": row.action_id,
        "action_number": action.number if action else "",
        "action_status": action.status if action else "",
        "package_status": package_status,
        "version": row.version,
        "statement": ENVIRONMENT_NOTE,
        "action_note": ACTION_LINK_NOTE,
    }


def supplement(db, user, project, payload):
    rows = db.query(HseEnvironmentRecord).filter_by(project_id=project.id).order_by(HseEnvironmentRecord.id.desc()).all()
    criteria = db.query(HseEnvironmentCriterion).filter_by(project_id=project.id).order_by(HseEnvironmentCriterion.name).all()
    payload["environment_note"] = ENVIRONMENT_NOTE
    payload["environment_action_note"] = ACTION_LINK_NOTE
    payload["environment_kinds"] = list(ENVIRONMENT_KINDS)
    payload["environment_results"] = list(ENVIRONMENT_RESULTS)
    payload["environment_criteria"] = [
        {"id": row.id, "name": row.name, "kind": row.kind, "threshold": row.threshold} for row in criteria
    ]
    payload["environment_records"] = [record_view(db, project, row) for row in rows]
    payload["counts"]["environment_records"] = len(rows)
    payload["counts"]["environment_outside"] = sum(row.result == "Outside criteria" for row in rows)
    return payload


def work_line():
    return {"environment_note": ENVIRONMENT_NOTE}
