"""Material take-off (MTO) for an exact drawing revision.

Extraction, import or manual entry creates an unverified draft. A discipline reviewer with
drawings.review verifies it. Verification is separate from requirement approval. A verified MTO
becomes one draft requirement in Requirements & Requests, linked line by line.
"""

import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy import update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.domains.coordination.jobs import notify
from app.domains.identity_projects.models import Discipline, Membership, User

from . import extraction
from .models import (
    Drawing,
    DrawingRevision,
    ExtractionJob,
    MaterialTakeoff,
    StoredFile,
    TakeoffCorrection,
    TakeoffLine,
)
from .workflow import _can, _drawing, _membership_allows, _user_name, read_file, sees_unreleased

RECORD = "engineering.takeoff"
EDITABLE = {"Draft", "Returned", "Pending Verification", "Extraction failed", "Needs setup"}
CLOSED_REQUIREMENTS = {"Cancelled", "Rejected"}
STALLED_AFTER = timedelta(minutes=15)
FIELDS = ("description", "specification", "quantity", "unit", "item_id", "reference", "page")


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _amount(value):
    return None if value is None else Decimal(str(value))


def _text(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f") if value == value.to_integral() else format(value, "f")
    return str(value)


def _bump(db, row, version):
    result = db.execute(
        update(MaterialTakeoff)
        .where(MaterialTakeoff.id == row.id, MaterialTakeoff.version == version)
        .values(version=version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "This MTO changed. Reload it and try again")
    db.refresh(row)


def revision_for(db, user, project, drawing, revision_id):
    revision = db.get(DrawingRevision, revision_id)
    if not revision or revision.drawing_id != drawing.id:
        raise HTTPException(404, "Revision not found")
    if not sees_unreleased(db, user, project) and revision.release_state not in {
        "Released",
        "Superseded",
        "Withdrawn",
    }:
        raise HTTPException(404, "Revision not found")
    return revision


def load(db, user, project, takeoff_id):
    row = db.get(MaterialTakeoff, takeoff_id)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "MTO not found")
    drawing = _drawing(db, user, project, row.drawing_id)
    revision_for(db, user, project, drawing, row.revision_id)
    return row, drawing


def can_edit(db, user, project, discipline_id):
    return _can(db, user, project, "drawings.edit", discipline_id) or _can(
        db, user, project, "procurement.requirement.edit", discipline_id
    )


def _require_edit(db, user, project, discipline_id):
    if not can_edit(db, user, project, discipline_id):
        raise HTTPException(403, "Preparing an MTO needs drawing edit or requirement edit access for this discipline")


def can_verify(db, user, project, row):
    return _membership_allows(db, user, project, "drawings.review", row.discipline_id)


def _reviewers(db, project, discipline_id):
    people = []
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        person = db.get(User, member.user_id)
        if not person or not person.active or person in people:
            continue
        if _membership_allows(db, person, project, "drawings.review", discipline_id):
            people.append(person)
    return people


def _log(db, user, row, kind, line=None, field="", old="", new=""):
    db.add(
        TakeoffCorrection(
            takeoff_id=row.id,
            line_id=line.id if line else None,
            kind=kind,
            field=field,
            old_value=_text(old),
            new_value=_text(new),
            actor_id=user.id,
        )
    )


def _number(db, drawing, revision):
    count = db.query(MaterialTakeoff).filter_by(drawing_id=drawing.id).count()
    return f"MTO-{drawing.number}-{revision.code}-{count + 1}"


def _new(db, user, project, drawing, revision, source, pages, dedupe_key, status):
    row = MaterialTakeoff(
        organization_id=project.organization_id,
        project_id=project.id,
        drawing_id=drawing.id,
        revision_id=revision.id,
        discipline_id=drawing.discipline_id,
        number=_number(db, drawing, revision),
        source=source,
        pages=pages,
        dedupe_key=dedupe_key,
        status=status,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    _log(db, user, row, "created", new=source)
    return row


def _existing(db, revision, dedupe_key):
    return db.query(MaterialTakeoff).filter_by(revision_id=revision.id, dedupe_key=dedupe_key).first()


def start_extraction(db, user, project, drawing, revision, pages):
    _require_edit(db, user, project, drawing.discipline_id)
    try:
        pages = extraction.validate_pages(pages)
    except extraction.ExtractionProblem as exc:
        raise HTTPException(422, str(exc)) from exc
    key = f"extract:{pages or 'all'}"
    found = _existing(db, revision, key)
    if found:
        return found, None
    row = _new(db, user, project, drawing, revision, "Extraction", pages, key, "Extracting")
    job = ExtractionJob(takeoff_id=row.id, created_by=user.id, status="Queued")
    db.add(job)
    db.flush()
    return row, job


def retry(db, user, project, row):
    _require_edit(db, user, project, row.discipline_id)
    if row.source != "Extraction":
        raise HTTPException(409, "Only an extracted MTO can be retried")
    job = latest_job(db, row)
    if job and job.status in {"Queued", "Running"} and not _stalled(job):
        raise HTTPException(409, "Extraction is still running")
    if row.status not in {"Extraction failed", "Needs setup", "Extracting"}:
        raise HTTPException(409, "Extraction already produced lines. Correct them on the review screen")
    if db.query(TakeoffLine).filter_by(takeoff_id=row.id, deleted=False).first():
        raise HTTPException(409, "Lines were already entered on this MTO. Correct them instead of re-extracting")
    row.status = "Extracting"
    row.note = ""
    fresh = ExtractionJob(
        takeoff_id=row.id,
        created_by=user.id,
        status="Queued",
        attempt=(job.attempt + 1) if job else 1,
    )
    db.add(fresh)
    _log(db, user, row, "retried")
    db.flush()
    return fresh


def run_extraction(bind, job_id):
    """Runs after the response is sent, in its own session."""
    with Session(bind=bind, expire_on_commit=False) as db:
        job = db.get(ExtractionJob, job_id)
        if not job or job.status != "Queued":
            return
        job.status = "Running"
        job.started_at = _now()
        db.commit()
        row = db.get(MaterialTakeoff, job.takeoff_id)
        revision = db.get(DrawingRevision, row.revision_id)
        stored = db.get(StoredFile, revision.file_id)
        try:
            if not stored or stored.scan_status == "quarantined":
                raise extraction.ExtractionProblem("The controlled drawing file is not available")
            lines, provider, message = extraction.extract(
                read_file(stored), stored.original_name, stored.content_type, row.pages
            )
        except extraction.ExtractionProblem as exc:
            job.status = "Needs setup" if exc.status == "Needs setup" else "Failed"
            job.message = str(exc)
            job.finished_at = _now()
            row.status = "Needs setup" if exc.status == "Needs setup" else "Extraction failed"
            row.note = str(exc)
            _alert_creator(db, row, "MTO extraction could not finish", f"{row.number}: {exc}", "failed", job)
            db.commit()
            return
        except Exception as exc:  # noqa: BLE001 - the user sees a clear failure instead of a stuck job
            db.rollback()
            job = db.get(ExtractionJob, job_id)
            row = db.get(MaterialTakeoff, job.takeoff_id)
            job.status = "Failed"
            job.message = f"Extraction stopped with an internal error ({exc.__class__.__name__}). Retry or enter lines by hand."
            job.finished_at = _now()
            row.status = "Extraction failed"
            row.note = job.message
            db.commit()
            return
        for position, line in enumerate(lines, start=1):
            db.add(
                TakeoffLine(
                    takeoff_id=row.id,
                    position=position,
                    description=line["description"],
                    specification=line["specification"],
                    quantity=line["quantity"],
                    unit=line["unit"],
                    reference=line["reference"],
                    page=line["page"],
                    table_ref=line["table_ref"],
                    row_ref=line["row_ref"],
                    bbox=line["bbox"],
                    confidence=line["confidence"],
                    flags=line["flags"],
                    origin="Extracted",
                    original=_original(line),
                )
            )
        job.status = "Succeeded"
        job.provider = provider
        job.message = message
        job.finished_at = _now()
        row.status = "Draft"
        row.note = message
        project = _project(db, row)
        drawing = db.get(Drawing, row.drawing_id)
        for person in _reviewers(db, project, row.discipline_id):
            notify(
                db,
                person,
                "MTO extraction ready for review",
                f"{row.number} for {drawing.number} rev {revision.code}: {message}",
                f"takeoff:{row.id}:job:{job.id}:ready",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )
        _alert_creator(db, row, "MTO extraction ready", f"{row.number}: {message}", "ready", job)
        db.commit()


def _project(db, row):
    from app.domains.identity_projects.models import Project

    return db.get(Project, row.project_id)


def _alert_creator(db, row, title, body, kind, job):
    person = db.get(User, row.created_by)
    if person:
        notify(
            db,
            person,
            title,
            body,
            f"takeoff:{row.id}:job:{job.id}:{kind}:creator",
            project_id=row.project_id,
            link=f"/projects/{row.project_id}",
        )


def _original(line):
    return {
        "description": line["description"],
        "specification": line["specification"],
        "quantity": _text(line["quantity"]) if line["quantity"] is not None else None,
        "unit": line["unit"],
        "reference": line["reference"],
        "page": line["page"],
        "table_ref": line["table_ref"],
        "row_ref": line["row_ref"],
        "flags": list(line["flags"]),
        **({"cells": line["original"]["cells"]} if line.get("original") else {}),
    }


def create_manual(db, user, project, drawing, revision):
    _require_edit(db, user, project, drawing.discipline_id)
    open_manual = (
        db.query(MaterialTakeoff)
        .filter_by(revision_id=revision.id, source="Manual")
        .filter(MaterialTakeoff.status.in_(EDITABLE))
        .first()
    )
    if open_manual:
        return open_manual, False
    count = db.query(MaterialTakeoff).filter_by(revision_id=revision.id, source="Manual").count()
    return _new(db, user, project, drawing, revision, "Manual", "", f"manual:{count + 1}", "Draft"), True


IMPORT_ALIASES = {
    "description": "description", "item description": "description", "material": "description",
    "material description": "description", "item": "description",
    "specification": "specification", "spec": "specification", "size": "specification",
    "quantity": "quantity", "qty": "quantity",
    "unit": "unit", "uom": "unit",
    "item code": "item_code", "catalogue code": "item_code", "catalog code": "item_code", "code": "item_code",
    "page": "page", "sheet": "page",
    "reference": "reference", "mark": "reference", "tag": "reference", "ref": "reference",
}


def import_list(db, user, project, drawing, revision, filename, payload, mode):
    import hashlib
    import re

    _require_edit(db, user, project, drawing.discipline_id)
    if mode not in {"preview", "confirm"}:
        raise HTTPException(422, "Import mode must be preview or confirm")
    if not payload:
        raise HTTPException(422, "The file is empty")
    from .workflow import read_records

    records = read_records(filename, payload)
    if not records:
        raise HTTPException(422, "The file has no header row")

    def header(cell):
        key = re.sub(r"[^a-z0-9]+", " ", str(cell or "").casefold()).strip()
        return IMPORT_ALIASES.get(key, key.replace(" ", "_"))

    columns = [header(cell) for cell in records[0]]
    missing = [name for name in ("description", "quantity", "unit") if name not in columns]
    if missing:
        raise HTTPException(
            422,
            f"Missing column(s): {', '.join(missing)}. Use: description, specification, quantity, unit, item_code, page, reference",
        )
    from app.domains.supply_chain.models import ProcurementItem

    catalogue = {
        row.code_key: row
        for row in db.query(ProcurementItem).filter_by(organization_id=user.organization_id, active=True)
    }
    rows = []
    for index, record in enumerate(records[1:], start=2):
        raw = {columns[i]: record[i] for i in range(min(len(columns), len(record))) if columns[i]}
        cells = {key: str(value if value is not None else "").strip() for key, value in raw.items()}
        if not any(cells.values()):
            continue
        flags = []
        quantity = None
        if not cells.get("quantity"):
            flags.append("Missing quantity")
        else:
            try:
                quantity = Decimal(cells["quantity"].replace(",", "."))
                if quantity <= 0:
                    flags.append(f"Quantity '{cells['quantity']}' is not above zero")
                    quantity = None
            except InvalidOperation:
                flags.append(f"Quantity '{cells['quantity']}' is not a number")
        unit = cells.get("unit", "")[:20]
        if not unit:
            flags.append("Missing unit")
        elif extraction.unit_key(unit) not in extraction.KNOWN_UNITS:
            flags.append(f"Unit '{unit}' is not a recognised unit")
        item = catalogue.get(cells.get("item_code", "").casefold()) if cells.get("item_code") else None
        if cells.get("item_code") and not item:
            flags.append(f"Catalogue code '{cells['item_code']}' was not found")
        page = cells.get("page", "")
        rows.append(
            {
                "row": index,
                "description": cells.get("description", "")[:2000],
                "specification": cells.get("specification", "")[:2000],
                "quantity": quantity,
                "unit": unit,
                "item_id": item.id if item else None,
                "item_code": item.code if item else "",
                "reference": cells.get("reference", "")[:80],
                "page": int(page) if page.isdigit() else None,
                "flags": flags,
                "cells": cells,
            }
        )
    rows = [row for row in rows if row["description"] or row["quantity"] is not None]
    preview = [
        {**row, "quantity": _text(row["quantity"]) if row["quantity"] is not None else None, "cells": None}
        for row in rows
    ]
    if mode == "preview":
        return None, preview
    if not rows:
        raise HTTPException(422, "No material rows were found in the file")
    digest = hashlib.sha256(payload).hexdigest()[:40]
    found = _existing(db, revision, f"import:{digest}")
    if found:
        return found, preview
    row = _new(db, user, project, drawing, revision, "Import", "", f"import:{digest}", "Draft")
    row.note = f"{len(rows)} line(s) imported from {filename or 'a file'}."
    for position, item in enumerate(rows, start=1):
        db.add(
            TakeoffLine(
                takeoff_id=row.id,
                position=position,
                description=item["description"],
                specification=item["specification"],
                quantity=item["quantity"],
                unit=item["unit"],
                item_id=item["item_id"],
                reference=item["reference"],
                page=item["page"],
                row_ref=str(item["row"]),
                table_ref="Import",
                flags=item["flags"],
                origin="Imported",
                original={
                    "cells": item["cells"],
                    "quantity": _text(item["quantity"]) if item["quantity"] is not None else None,
                    "unit": item["unit"],
                    "flags": list(item["flags"]),
                },
            )
        )
    db.flush()
    return row, preview


def _editable(db, user, project, row, version):
    _require_edit_or_verify(db, user, project, row)
    if row.status not in EDITABLE:
        raise HTTPException(409, f"A {row.status.lower()} MTO cannot be changed")
    _bump(db, row, version)
    if row.status in {"Extraction failed", "Needs setup"}:
        row.status = "Draft"


def _require_edit_or_verify(db, user, project, row):
    if not can_edit(db, user, project, row.discipline_id) and not can_verify(db, user, project, row):
        raise HTTPException(403, "Correcting an MTO needs drawing edit, requirement edit or drawing review access")


def _clean(data, db, user, project, row):
    values = {}
    if "description" in data:
        values["description"] = (data["description"] or "").strip()[:2000]
    if "specification" in data:
        values["specification"] = (data["specification"] or "").strip()[:2000]
    if "quantity" in data:
        raw = data["quantity"]
        if raw in (None, ""):
            values["quantity"] = None
        else:
            try:
                quantity = Decimal(str(raw))
            except InvalidOperation as exc:
                raise HTTPException(422, "Quantity must be a number") from exc
            if quantity <= 0:
                raise HTTPException(422, "Quantity must be above zero")
            values["quantity"] = quantity.quantize(Decimal("0.001"))
    if "unit" in data:
        values["unit"] = (data["unit"] or "").strip()[:20]
    if "reference" in data:
        values["reference"] = (data["reference"] or "").strip()[:80]
    if "page" in data:
        values["page"] = data["page"] or None
    if "item_id" in data:
        item_id = data["item_id"] or None
        if item_id:
            from app.domains.supply_chain.models import ProcurementItem

            item = db.get(ProcurementItem, item_id)
            if not item or item.organization_id != user.organization_id or not item.active:
                raise HTTPException(422, "Choose an active catalogue item")
        values["item_id"] = item_id
    return values


def _review_flags(db, line):
    from app.domains.supply_chain.models import ProcurementItem, UnitConversion

    flags = []
    if line.quantity is None:
        flags.append("Missing quantity")
    if not line.unit:
        flags.append("Missing unit")
    elif extraction.unit_key(line.unit) not in extraction.KNOWN_UNITS:
        flags.append(f"Unit '{line.unit}' is not a recognised unit")
    if not line.item_id:
        flags.append("No catalogue item")
    else:
        item = db.get(ProcurementItem, line.item_id)
        if item and line.unit and line.unit.casefold() != item.base_unit.casefold():
            conversion = (
                db.query(UnitConversion)
                .filter_by(organization_id=item.organization_id, from_unit=line.unit, to_unit=item.base_unit)
                .first()
                or db.query(UnitConversion)
                .filter_by(organization_id=item.organization_id, from_unit=item.base_unit, to_unit=line.unit)
                .first()
            )
            if not conversion:
                flags.append(f"Unit {line.unit} differs from catalogue unit {item.base_unit} and has no conversion")
    if line.confidence is not None and Decimal(str(line.confidence)) < Decimal("0.6"):
        flags.append("Low extraction confidence")
    return flags


def add_line(db, user, project, row, data):
    _editable(db, user, project, row, data.get("version"))
    values = _clean(data, db, user, project, row)
    if not values.get("description"):
        raise HTTPException(422, "Enter a description")
    position = (
        db.query(TakeoffLine).filter_by(takeoff_id=row.id).count() + 1
    )
    line = TakeoffLine(takeoff_id=row.id, position=position, origin="Added", flags=[], **values)
    db.add(line)
    db.flush()
    _log(db, user, row, "line added", line, "description", "", line.description)
    return line


def edit_line(db, user, project, row, line_id, data):
    line = db.get(TakeoffLine, line_id)
    if not line or line.takeoff_id != row.id or line.deleted:
        raise HTTPException(404, "MTO line not found")
    values = _clean(data, db, user, project, row)
    if row.status == "Verified":
        if set(values) - {"item_id"}:
            raise HTTPException(409, "A verified MTO only accepts catalogue matching. Quantities and units stay as verified")
        if _requirements(db, row):
            raise HTTPException(409, "A requirement already uses this MTO")
        _require_edit(db, user, project, row.discipline_id)
        _bump(db, row, data.get("version"))
    else:
        _editable(db, user, project, row, data.get("version"))
    for field, value in values.items():
        old = getattr(line, field)
        if _text(old) == _text(value):
            continue
        setattr(line, field, value)
        _log(db, user, row, "corrected", line, field, old, value)
    line.version += 1
    return line


def delete_line(db, user, project, row, line_id, version, reason):
    line = db.get(TakeoffLine, line_id)
    if not line or line.takeoff_id != row.id or line.deleted:
        raise HTTPException(404, "MTO line not found")
    _editable(db, user, project, row, version)
    line.deleted = True
    _log(db, user, row, "line deleted", line, "reason", "", reason or "")


def submit(db, user, project, row, version):
    _require_edit(db, user, project, row.discipline_id)
    if row.status not in {"Draft", "Returned"}:
        raise HTTPException(409, "Only a draft or returned MTO is sent for verification")
    if not db.query(TakeoffLine).filter_by(takeoff_id=row.id, deleted=False).first():
        raise HTTPException(422, "Add at least one material line")
    _bump(db, row, version)
    row.status = "Pending Verification"
    row.submitted_by = user.id
    row.return_reason = ""
    _log(db, user, row, "sent for verification")
    from app.domains.coordination.service import _task

    drawing = db.get(Drawing, row.drawing_id)
    owner = None
    reviewers = _reviewers(db, project, row.discipline_id)
    for candidate in (drawing.reviewer_id, drawing.responsible_user_id):
        if candidate and candidate != user.id and any(person.id == candidate for person in reviewers):
            owner = candidate
            break
    if owner is None:
        owner = next((person.id for person in reviewers if person.id != user.id), None)
    if owner:
        _task(db, user, project, owner, f"Verify {row.number}", RECORD, row.id)
    for person in reviewers:
        notify(
            db,
            person,
            "MTO ready for verification",
            f"{row.number} for {drawing.number} is waiting for discipline verification.",
            f"takeoff:{row.id}:v{row.version}:submitted",
            project_id=project.id,
            link=f"/projects/{project.id}",
        )


def _active_lines(db, row):
    return (
        db.query(TakeoffLine)
        .filter_by(takeoff_id=row.id, deleted=False)
        .order_by(TakeoffLine.position)
        .all()
    )


def verify(db, user, project, row, version):
    if not can_verify(db, user, project, row):
        raise HTTPException(403, "MTO verification needs drawing review access for this discipline")
    if row.status != "Pending Verification":
        raise HTTPException(409, "Only an MTO sent for verification can be verified")
    if user.id in {row.created_by, row.submitted_by}:
        raise HTTPException(403, "The person who prepared or sent this MTO cannot verify it")
    lines = _active_lines(db, row)
    if not lines:
        raise HTTPException(422, "Add at least one material line")
    unresolved = [line.position for line in lines if line.quantity is None or not line.unit]
    if unresolved:
        raise HTTPException(
            422,
            "Line(s) " + ", ".join(map(str, unresolved)) + " have no quantity or unit. Enter them from the drawing or delete the line.",
        )
    mismatched = [
        line.position for line in lines if any("has no conversion" in flag for flag in _review_flags(db, line))
    ]
    if mismatched:
        raise HTTPException(
            422,
            "Line(s) " + ", ".join(map(str, mismatched)) + " use a unit that differs from the catalogue item without a conversion.",
        )
    _bump(db, row, version)
    row.status = "Verified"
    row.verified_by = user.id
    row.verified_at = _now()
    _log(db, user, row, "verified")
    from app.domains.coordination.service import _close_tasks

    _close_tasks(db, project.id, RECORD, row.id, "Completed", f"Verified by {user.name}")
    _compare_with_previous(db, user, project, row)


def return_for_correction(db, user, project, row, version, reason):
    if not can_verify(db, user, project, row):
        raise HTTPException(403, "Returning an MTO needs drawing review access for this discipline")
    if row.status != "Pending Verification":
        raise HTTPException(409, "Only an MTO sent for verification can be returned")
    if not (reason or "").strip():
        raise HTTPException(422, "Enter what needs to be corrected")
    _bump(db, row, version)
    row.status = "Returned"
    row.return_reason = reason.strip()
    _log(db, user, row, "returned", new=reason.strip())
    from app.domains.coordination.service import _close_tasks, _task

    _close_tasks(db, project.id, RECORD, row.id, "Completed", "Returned for correction")
    requester = row.submitted_by or row.created_by
    _task(db, user, project, requester, f"Correct {row.number}: {reason.strip()[:120]}", RECORD, row.id)


def cancel(db, user, project, row, version, reason):
    _require_edit(db, user, project, row.discipline_id)
    if row.status in {"Cancelled", "Superseded"}:
        raise HTTPException(409, "This MTO is already closed")
    if _requirements(db, row):
        raise HTTPException(409, "A requirement uses this MTO. Cancel the requirement first")
    _bump(db, row, version)
    row.status = "Cancelled"
    row.dedupe_key = f"cancelled:{row.id}"
    _log(db, user, row, "cancelled", new=reason or "")
    from app.domains.coordination.service import _close_tasks

    _close_tasks(db, project.id, RECORD, row.id, "Cancelled", "MTO cancelled")


def _requirements(db, row):
    from app.domains.supply_chain.models import MaterialRequirement

    return (
        db.query(MaterialRequirement)
        .filter(MaterialRequirement.takeoff_id == row.id)
        .filter(MaterialRequirement.status.notin_(CLOSED_REQUIREMENTS))
        .all()
    )


def _key(line):
    if line.item_id:
        return f"item:{line.item_id}"
    return "text:" + " ".join(str(line.description or "").casefold().split())


def _label(db, line):
    if line.item_id:
        from app.domains.supply_chain.models import ProcurementItem

        item = db.get(ProcurementItem, line.item_id)
        if item:
            return f"{item.code} · {item.description}"
    return line.description


def _totals(db, lines):
    result = {}
    for line in lines:
        entry = result.setdefault(
            _key(line),
            {"label": _label(db, line), "quantity": Decimal("0"), "unit": line.unit, "specs": []},
        )
        entry["quantity"] += _amount(line.quantity) or Decimal("0")
        spec = (line.specification or "").strip()
        if spec and spec not in entry["specs"]:
            entry["specs"].append(spec)
    return result


def diff(db, old_row, new_row):
    old = _totals(db, _active_lines(db, old_row))
    new = _totals(db, _active_lines(db, new_row))
    result = {"added": [], "removed": [], "quantity_changed": [], "specification_changed": []}
    for key, entry in new.items():
        if key not in old:
            result["added"].append(
                {"label": entry["label"], "quantity": _text(entry["quantity"]), "unit": entry["unit"], "specification": "; ".join(entry["specs"])}
            )
            continue
        before = old[key]
        if before["quantity"] != entry["quantity"] or before["unit"] != entry["unit"]:
            result["quantity_changed"].append(
                {
                    "label": entry["label"],
                    "old": f"{_text(before['quantity'])} {before['unit']}".strip(),
                    "new": f"{_text(entry['quantity'])} {entry['unit']}".strip(),
                }
            )
        if sorted(before["specs"]) != sorted(entry["specs"]):
            result["specification_changed"].append(
                {"label": entry["label"], "old": "; ".join(before["specs"]), "new": "; ".join(entry["specs"])}
            )
    for key, entry in old.items():
        if key not in new:
            result["removed"].append(
                {"label": entry["label"], "quantity": _text(entry["quantity"]), "unit": entry["unit"], "specification": "; ".join(entry["specs"])}
            )
    return result


def _summary_text(changes):
    parts = []
    for key, label in (
        ("added", "added"),
        ("removed", "removed"),
        ("quantity_changed", "quantity changed"),
        ("specification_changed", "specification changed"),
    ):
        if changes[key]:
            parts.append(f"{len(changes[key])} {label}")
    return ", ".join(parts) or "no material differences"


def _previous(db, row):
    revision = db.get(DrawingRevision, row.revision_id)
    candidates = []
    for other in db.query(MaterialTakeoff).filter(
        MaterialTakeoff.drawing_id == row.drawing_id,
        MaterialTakeoff.id != row.id,
        MaterialTakeoff.status == "Verified",
    ):
        other_revision = db.get(DrawingRevision, other.revision_id)
        if other_revision and other_revision.sequence < revision.sequence:
            candidates.append((other_revision.sequence, other.id, other))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def _affected(db, requirements):
    from app.domains.supply_chain.models import (
        FulfilmentAllocation,
        PurchaseOrder,
        PurchaseOrderLine,
        PurchaseRequisition,
        QuotationLine,
        RequirementLine,
        RequisitionLine,
        RfqAward,
        RfqLine,
    )

    requisitions, orders, allocations = {}, {}, 0
    for requirement in requirements:
        for line in db.query(RequirementLine).filter_by(requirement_id=requirement.id):
            allocations += (
                db.query(FulfilmentAllocation).filter_by(requirement_line_id=line.id, status="Active").count()
            )
            for pr_line in db.query(RequisitionLine).filter_by(requirement_line_id=line.id):
                pr = db.get(PurchaseRequisition, pr_line.requisition_id)
                if pr and pr.status not in {"Cancelled", "Rejected"}:
                    requisitions[pr.id] = {"id": pr.id, "number": pr.number, "status": pr.status, "owner": pr.created_by}
                for rfq_line in db.query(RfqLine).filter_by(requisition_line_id=pr_line.id):
                    for quote_line in db.query(QuotationLine).filter_by(rfq_line_id=rfq_line.id):
                        for award in db.query(RfqAward).filter_by(quotation_line_id=quote_line.id):
                            for po_line in db.query(PurchaseOrderLine).filter_by(award_id=award.id):
                                po = db.get(PurchaseOrder, po_line.purchase_order_id)
                                if po and po.status not in {"Cancelled", "Closed"}:
                                    orders[po.id] = {"id": po.id, "number": po.number, "status": po.status, "owner": po.created_by}
    return list(requisitions.values()), list(orders.values()), allocations


def _compare_with_previous(db, user, project, row):
    previous = _previous(db, row)
    if not previous:
        return
    row.previous_id = previous.id
    changes = diff(db, previous, row)
    requirements = _requirements(db, previous)
    requisitions, orders, allocations = _affected(db, requirements)
    previous.status = "Superseded"
    _log(db, user, previous, "superseded", new=row.number)
    summary = {
        **changes,
        "previous": previous.number,
        "requirements": [{"id": item.id, "number": item.number, "status": item.status} for item in requirements],
        "requisitions": [{key: value for key, value in item.items() if key != "owner"} for item in requisitions],
        "orders": [{key: value for key, value in item.items() if key != "owner"} for item in orders],
        "allocations": allocations,
        "text": _summary_text(changes),
    }
    row.change_summary = summary
    flag_modified(row, "change_summary")
    if not requirements:
        row.change_state = "No linked requirement"
        return
    row.change_state = "Review required"
    drawing = db.get(Drawing, row.drawing_id)
    revision = db.get(DrawingRevision, row.revision_id)
    detail = (
        f"{drawing.number} rev {revision.code} MTO {row.number} replaces {previous.number}: {summary['text']}. "
        f"{len(requisitions)} requisition(s), {len(orders)} order(s) and {allocations} stock allocation(s) are linked."
    )
    from app.domains.coordination.service import _task
    from app.domains.supply_chain.service import REQUIREMENT, _event, role_allows

    recipients = {}
    for requirement in requirements:
        if requirement.impact_state == "Review required":
            if detail not in (requirement.impact_detail or ""):
                requirement.impact_detail = f"{requirement.impact_detail} {detail}".strip()
        else:
            requirement.impact_state = "Review required"
            requirement.impact_detail = detail
            _task(db, user, project, requirement.requested_by, f"Review drawing impact on {requirement.number}", REQUIREMENT, requirement.id)
        requirement.version += 1
        _event(db, user, project.id, "requirements", requirement.id, "impact", detail)
        recipients[requirement.requested_by] = True
    for item in requisitions + orders:
        recipients[item["owner"]] = True
    if drawing.responsible_user_id:
        recipients[drawing.responsible_user_id] = True
    for member in db.query(Membership).filter_by(project_id=project.id, active=True):
        person = db.get(User, member.user_id)
        if person and role_allows(db, person, project, "procurement.requisition.edit"):
            recipients[person.id] = True
    for person_id in recipients:
        person = db.get(User, person_id)
        if person and person.active:
            notify(
                db,
                person,
                "Drawing revision affects a requirement",
                detail,
                f"takeoff:{row.id}:revision-impact",
                project_id=project.id,
                link=f"/projects/{project.id}",
            )


def apply_changes(db, user, project, row, version):
    """Moves the linked requirement to the new verified MTO. The requirement returns to Draft for approval."""
    from app.domains.supply_chain.models import MaterialRequirement, RequirementLine
    from app.domains.supply_chain.service import (
        _event,
        _reserved,
        _stamp,
        permitted,
    )
    from app.domains.supply_chain.fulfilment import allocated

    if row.change_state != "Review required" or not row.previous_id:
        raise HTTPException(409, "This MTO has no revision change waiting to be applied")
    previous = db.get(MaterialTakeoff, row.previous_id)
    requirements = _requirements(db, previous)
    if not requirements:
        raise HTTPException(409, "No open requirement uses the previous MTO")
    for requirement in requirements:
        permitted(db, user, project, "procurement.requirement.edit", requirement.discipline_id)
        if requirement.impact_state == "Review required":
            raise HTTPException(409, f"The requirement reviewer records the impact decision on {requirement.number} first")
        if requirement.status == "Pending Approval":
            raise HTTPException(409, f"{requirement.number} is in review. The reviewer returns it first")
    lines = _active_lines(db, row)
    unmatched = [line.position for line in lines if not line.item_id]
    if unmatched:
        raise HTTPException(422, "Match a catalogue item on MTO line(s) " + ", ".join(map(str, unmatched)))
    _bump(db, row, version)
    revision = db.get(DrawingRevision, row.revision_id)
    for requirement in requirements:
        current = {}
        for existing in db.query(RequirementLine).filter_by(requirement_id=requirement.id):
            source = db.get(TakeoffLine, existing.takeoff_line_id) if existing.takeoff_line_id else None
            current.setdefault(_key(source) if source else f"item:{existing.item_id}", existing)
        wanted = {}
        for line in lines:
            wanted.setdefault(_key(line), []).append(line)
        position = 0
        for key, group in wanted.items():
            total = sum((_amount(line.quantity) for line in group), Decimal("0"))
            first = group[0]
            target = current.pop(key, None)
            reserved, _approved = _reserved(db, target.id) if target else (Decimal("0"), Decimal("0"))
            held = reserved + (allocated(db, target.id) if target else Decimal("0"))
            if total < held:
                raise HTTPException(
                    422,
                    f"{_label(db, first)}: the new quantity {_text(total)} is below {_text(held)} already on requisitions or allocated stock",
                )
            position += 1
            if target is None:
                target = RequirementLine(requirement_id=requirement.id, required_date=requirement.required_date)
                db.add(target)
            target.position = position
            target.item_id = first.item_id
            target.specification = "; ".join(dict.fromkeys(line.specification for line in group if line.specification))
            target.quantity = total
            target.unit = first.unit
            target.tag = first.reference
            target.engineering_reference = _reference(db, row, first)
            target.takeoff_line_id = first.id
            target.drawing_revision_id = revision.id
        for leftover in current.values():
            reserved, _approved = _reserved(db, leftover.id)
            if reserved > 0 or allocated(db, leftover.id) > 0:
                raise HTTPException(
                    422,
                    f"A removed line on {requirement.number} is already on a requisition or allocated stock. Cancel that first",
                )
            if _has_history(db, leftover):
                position += 1
                leftover.position = position
                leftover.quantity = Decimal("0.000")
                leftover.engineering_reference = f"Removed in rev {revision.code} · {row.number}"[:200]
            else:
                db.delete(leftover)
        if requirement.status == "Approved":
            requirement.status = "Draft"
            _event(db, user, project.id, "requirements", requirement.id, "amended", f"Revision change from {row.number}")
        requirement.takeoff_id = row.id
        requirement.drawing_revision_id = revision.id
        requirement.version += 1
        _stamp(requirement, user)
        _event(db, user, project.id, "requirements", requirement.id, "revision-applied", row.number)
    row.change_state = "Applied"
    _log(db, user, row, "revision change applied")


def _has_history(db, line):
    """Cancelled requisition lines and released allocations still point at this requirement line."""
    from app.domains.supply_chain.models import FulfilmentAllocation, RequisitionLine

    return (
        db.query(RequisitionLine).filter_by(requirement_line_id=line.id).first() is not None
        or db.query(FulfilmentAllocation).filter_by(requirement_line_id=line.id).first() is not None
    )


def _reference(db, row, line):
    drawing = db.get(Drawing, row.drawing_id)
    revision = db.get(DrawingRevision, row.revision_id)
    parts = [f"{drawing.number} rev {revision.code}", row.number]
    if line.page:
        parts.append(f"p{line.page}")
    if line.table_ref:
        parts.append(line.table_ref)
    if line.row_ref:
        parts.append(f"row {line.row_ref}")
    return " · ".join(parts)[:200]


class _LineIn:
    def __init__(self, line, required_date, reference):
        self.id = None
        self.item_id = line.item_id
        self.specification = line.specification
        self.quantity = line.quantity
        self.unit = line.unit
        self.required_date = required_date
        self.tag = line.reference
        self.engineering_reference = reference


class _RequirementIn:
    def __init__(self, data, row, drawing, lines, references):
        self.number = data.number
        self.company_id = data.company_id or drawing.company_id
        self.discipline_id = row.discipline_id
        self.area_id = drawing.area_id
        self.requested_by = data.requested_by
        self.required_date = data.required_date
        self.priority = data.priority
        self.purpose = data.purpose
        self.remarks = data.remarks
        self.drawing_id = drawing.id
        self.drawing_revision_id = row.revision_id
        self.lines = [_LineIn(line, data.required_date, references[line.id]) for line in lines]
        self.version = None


def create_requirement(db, user, project, row, data):
    from app.domains.supply_chain import service as supply
    from app.domains.supply_chain.models import RequirementLine

    if row.status != "Verified":
        raise HTTPException(409, "Only a verified MTO becomes a requirement")
    existing = _requirements(db, row)
    if existing:
        return existing[0], False
    if row.change_state == "Review required":
        raise HTTPException(409, "Apply or review the revision change first")
    supply.permitted(db, user, project, "procurement.requirement.edit", row.discipline_id)
    lines = _active_lines(db, row)
    unmatched = [line.position for line in lines if not line.item_id]
    if unmatched:
        raise HTTPException(
            422,
            "Match a catalogue item on MTO line(s) " + ", ".join(map(str, unmatched)) + " before creating the requirement",
        )
    _bump(db, row, data.version)
    drawing = db.get(Drawing, row.drawing_id)
    references = {line.id: _reference(db, row, line) for line in lines}
    requirement = supply.create_requirement(db, user, project, _RequirementIn(data, row, drawing, lines, references))
    requirement.source = "Drawing MTO"
    requirement.takeoff_id = row.id
    db.flush()
    stored = (
        db.query(RequirementLine)
        .filter_by(requirement_id=requirement.id)
        .order_by(RequirementLine.position)
        .all()
    )
    for created, line in zip(stored, lines):
        created.takeoff_line_id = line.id
        created.drawing_revision_id = row.revision_id
    _log(db, user, row, "requirement created", new=requirement.number)
    return requirement, True


def latest_job(db, row):
    return (
        db.query(ExtractionJob)
        .filter_by(takeoff_id=row.id)
        .order_by(ExtractionJob.id.desc())
        .first()
    )


def _stalled(job):
    started = _aware(job.started_at or job.created_at)
    return job.status in {"Queued", "Running"} and started and _now() - started > STALLED_AFTER


def _line_payload(db, row, line):
    from app.domains.supply_chain.models import ProcurementItem

    item = db.get(ProcurementItem, line.item_id) if line.item_id else None
    current = _review_flags(db, line)
    if line.origin != "Added" and _untouched(db, line):
        flags = list(dict.fromkeys(list(line.flags or []) + current))
    else:
        flags = current
    return {
        "id": line.id,
        "position": line.position,
        "description": line.description,
        "specification": line.specification,
        "quantity": _text(line.quantity) if line.quantity is not None else None,
        "unit": line.unit,
        "item_id": line.item_id,
        "item_code": item.code if item else "",
        "item_description": item.description if item else "",
        "reference": line.reference,
        "page": line.page,
        "table_ref": line.table_ref,
        "row_ref": line.row_ref,
        "bbox": line.bbox,
        "confidence": _text(line.confidence) if line.confidence is not None else None,
        "flags": flags,
        "origin": line.origin,
        "original": line.original,
        "corrected": not _untouched(db, line),
        "version": line.version,
    }


def _untouched(db, line):
    return line.version == 1


def payload(db, user, project, row, full=True):
    drawing = db.get(Drawing, row.drawing_id)
    revision = db.get(DrawingRevision, row.revision_id)
    job = latest_job(db, row)
    discipline = db.get(Discipline, row.discipline_id)
    requirements = _requirements(db, row)
    data = {
        "id": row.id,
        "number": row.number,
        "project_id": row.project_id,
        "drawing_id": drawing.id,
        "drawing_number": drawing.number,
        "drawing_title": drawing.title,
        "revision_id": revision.id,
        "revision_code": revision.code,
        "revision_release_state": revision.release_state,
        "discipline_id": row.discipline_id,
        "discipline": discipline.name if discipline else "",
        "source": row.source,
        "pages": row.pages,
        "status": row.status,
        "note": row.note,
        "return_reason": row.return_reason,
        "change_state": row.change_state,
        "change_summary": row.change_summary,
        "previous_id": row.previous_id,
        "created_by_name": _user_name(db, row.created_by),
        "created_at": row.created_at.isoformat(),
        "verified_by_name": _user_name(db, row.verified_by),
        "verified_at": row.verified_at.isoformat() if row.verified_at else "",
        "version": row.version,
        "line_count": db.query(TakeoffLine).filter_by(takeoff_id=row.id, deleted=False).count(),
        "requirements": [
            {"id": item.id, "number": item.number, "status": item.status} for item in requirements
        ],
        "job": None
        if not job
        else {
            "id": job.id,
            "status": "Stalled" if _stalled(job) else job.status,
            "provider": job.provider,
            "message": job.message
            or ("The extraction has not reported back for 15 minutes. Retry it." if _stalled(job) else ""),
            "attempt": job.attempt,
            "started_at": job.started_at.isoformat() if job.started_at else "",
            "finished_at": job.finished_at.isoformat() if job.finished_at else "",
        },
        "access": {
            "edit": row.status in EDITABLE
            and (can_edit(db, user, project, row.discipline_id) or can_verify(db, user, project, row)),
            "match": row.status == "Verified" and not requirements and can_edit(db, user, project, row.discipline_id),
            "submit": row.status in {"Draft", "Returned"} and can_edit(db, user, project, row.discipline_id),
            "verify": row.status == "Pending Verification"
            and can_verify(db, user, project, row)
            and user.id not in {row.created_by, row.submitted_by},
            "retry": row.source == "Extraction"
            and row.status in {"Extraction failed", "Needs setup", "Extracting"}
            and (not job or job.status not in {"Queued", "Running"} or _stalled(job))
            and can_edit(db, user, project, row.discipline_id),
            "requirement": row.status == "Verified"
            and not requirements
            and row.change_state != "Review required"
            and _can(db, user, project, "procurement.requirement.edit", row.discipline_id),
            "apply": row.change_state == "Review required"
            and _can(db, user, project, "procurement.requirement.edit", row.discipline_id),
            "cancel": row.status not in {"Cancelled", "Superseded"}
            and not requirements
            and can_edit(db, user, project, row.discipline_id),
        },
    }
    if not full:
        return data
    data["lines"] = [_line_payload(db, row, line) for line in _active_lines(db, row)]
    data["deleted_lines"] = [
        _line_payload(db, row, line)
        for line in db.query(TakeoffLine).filter_by(takeoff_id=row.id, deleted=True).order_by(TakeoffLine.position)
    ]
    data["history"] = [
        {
            "id": item.id,
            "kind": item.kind,
            "line_id": item.line_id,
            "field": item.field,
            "old": item.old_value,
            "new": item.new_value,
            "actor": _user_name(db, item.actor_id),
            "at": item.created_at.isoformat(),
        }
        for item in db.query(TakeoffCorrection)
        .filter_by(takeoff_id=row.id)
        .order_by(TakeoffCorrection.id)
    ]
    data["jobs"] = [
        {"id": item.id, "status": item.status, "provider": item.provider, "message": item.message, "attempt": item.attempt}
        for item in db.query(ExtractionJob).filter_by(takeoff_id=row.id).order_by(ExtractionJob.id)
    ]
    if row.status in {"Draft", "Returned", "Pending Verification"}:
        preview = compare_preview(db, row)
        if preview:
            data["change_summary"] = preview
    return data


def compare_preview(db, row):
    previous = _previous(db, row) if row.status != "Verified" else (
        db.get(MaterialTakeoff, row.previous_id) if row.previous_id else None
    )
    if not previous:
        return None
    changes = diff(db, previous, row)
    return {**changes, "previous": previous.number, "text": _summary_text(changes)}


EXPORT_HEADERS = [
    "MTO", "Drawing", "Revision", "Revision release state", "Verification status", "Verified by", "Verified at",
    "Line", "Description", "Specification", "Quantity", "Unit", "Catalogue code", "Reference",
    "Page", "Table", "Row", "Confidence", "Flags", "Origin", "Corrected",
]


def export(db, user, project, row, view, fmt):
    data = payload(db, user, project, row)
    status = "Not verified" if row.status != "Verified" else "Verified"
    if view == "original":
        status = "Unverified extraction (original values)"
    rows = []
    for line in data["lines"] + ([] if view != "original" else data["deleted_lines"]):
        original = line["original"] or {}
        values = line
        if view == "original":
            if not original:
                continue
            cells = original.get("cells") if isinstance(original.get("cells"), dict) else {}
            values = {
                **line,
                "description": original.get("description", cells.get("description", "")),
                "specification": original.get("specification", cells.get("specification", "")),
                "quantity": original.get("quantity"),
                "unit": original.get("unit", ""),
                "flags": original.get("flags", []),
                "item_code": "",
            }
        rows.append(
            [
                data["number"], data["drawing_number"], data["revision_code"], data["revision_release_state"],
                status, data["verified_by_name"] if view != "original" else "", data["verified_at"] if view != "original" else "",
                values["position"], values["description"], values["specification"],
                values["quantity"] if values["quantity"] is not None else "", values["unit"], values["item_code"],
                values["reference"], values["page"] or "", values["table_ref"], values["row_ref"],
                values["confidence"] or "", "; ".join(values["flags"]), values["origin"],
                "Yes" if line["corrected"] and view != "original" else "No",
            ]
        )
    notice = [f"Export only. Verification status: {status}. Exporting does not verify or approve this MTO."]
    if fmt == "xlsx":
        book = Workbook()
        sheet = book.active
        sheet.title = "MTO"
        sheet.append(notice)
        sheet.append(EXPORT_HEADERS)
        for item in rows:
            sheet.append(item)
        buffer = io.BytesIO()
        book.save(buffer)
        return buffer.getvalue()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(notice)
    writer.writerow(EXPORT_HEADERS)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def list_rows(db, user, project, drawing_id=None, status=""):
    query = db.query(MaterialTakeoff).filter_by(project_id=project.id)
    if drawing_id:
        query = query.filter_by(drawing_id=drawing_id)
    if status:
        query = query.filter(MaterialTakeoff.status == status)
    result = []
    for row in query.order_by(MaterialTakeoff.id.desc()).limit(200):
        try:
            drawing = _drawing(db, user, project, row.drawing_id)
            revision_for(db, user, project, drawing, row.revision_id)
        except HTTPException:
            continue
        result.append(payload(db, user, project, row, full=False))
    return result
