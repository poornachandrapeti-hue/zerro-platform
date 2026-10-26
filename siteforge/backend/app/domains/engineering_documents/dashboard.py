import csv
import io
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from app.domains.coordination.models import ReviewDecision, ReviewInstance
from app.domains.coordination.service import _reviewers, current_stage
from app.domains.identity_projects.models import Area, Company, Discipline, ProjectDiscipline, User
from .models import (
    Drawing,
    DrawingComment,
    DrawingRevision,
    EngineeringSetting,
    RevisionEvent,
    Transmittal,
    TransmittalItem,
)
from .workflow import (
    BUCKETS,
    DRAWING_REVIEW,
    _can,
    _client_label,
    _internal_label,
    _preparation_label,
    bucket_for,
    sees_unreleased,
)

METRICS = (
    ("total", "Total", "Unique drawings in the filtered register. Revisions, files, reviewers and comments never add to it."),
    ("to_prepare", "To Prepare", "Planned drawings with no revision uploaded yet."),
    ("preparing", "Preparing", "Preparation started or a revision exists but the current revision has not been submitted."),
    ("internal_review", "Internal Review", "Current revision is waiting on an internal review stage."),
    ("client_review", "Client Review", "Current revision is waiting on the client review stage."),
    ("open_comments", "Open Comments", "Drawings with at least one comment that is not closed, on any revision."),
    ("returned", "Returned / Rejected", "Current revision was returned for correction or rejected and needs a new revision."),
    ("approved", "Approved", "Current revision has a client outcome of Approved or Approved with Comments. Internal acceptance alone is not counted."),
    ("released", "Released", "Drawings with an authorized construction revision. That revision can be older than the current one."),
    ("overdue", "Overdue", "At least one dated action is past due and not complete. The register shows which action."),
)
METRIC_KEYS = tuple(key for key, _label, _text in METRICS)
BUCKET_LABELS = {
    "to_prepare": "Not started",
    "in_preparation": "In preparation",
    "under_review": "Under review",
    "accepted": "Accepted, not released",
    "accepted_with_comments": "Accepted with comments, not released",
    "returned": "Returned",
    "rejected": "Rejected",
    "released": "Current revision released",
}
RELEASE_STATUSES = ("Released", "Released, newer revision in progress", "Eligible for release", "Withdrawn", "Not released")
SORTS = {
    "number": lambda r: r["number"].lower(),
    "title": lambda r: r["title"].lower(),
    "discipline": lambda r: r["discipline"].lower(),
    "required_date": lambda r: r["required_date"] or date.max,
    "days_overdue": lambda r: r["days_overdue"],
    "open_comments": lambda r: r["open_comments"],
    "last_updated": lambda r: r["last_updated"] or datetime.min.replace(tzinfo=timezone.utc),
}
UPCOMING_DAYS = 14


def _aware(value):
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def accessible_disciplines(db, user, project):
    enabled = [
        row.discipline_id
        for row in db.query(ProjectDiscipline).filter_by(project_id=project.id, active=True)
    ]
    rows = []
    for discipline_id in enabled:
        if _can(db, user, project, "drawings.view", discipline_id):
            found = db.get(Discipline, discipline_id)
            if found:
                rows.append({"id": found.id, "name": found.name})
    return sorted(rows, key=lambda row: row["name"].lower())


def _names(db):
    cache = {}

    def name(user_id):
        if not user_id:
            return ""
        if user_id not in cache:
            person = db.get(User, user_id)
            cache[user_id] = person.name if person else f"User {user_id}"
        return cache[user_id]

    return name


def _pending_reviewers(db, revision, name):
    instance = (
        db.query(ReviewInstance)
        .filter_by(record_type=DRAWING_REVIEW, record_id=revision.id, state="In Review")
        .order_by(ReviewInstance.id.desc())
        .first()
    )
    if not instance:
        return []
    stage = current_stage(db, instance)
    if not stage:
        return []
    done = {
        row.reviewer_id
        for row in db.query(ReviewDecision).filter_by(
            instance_id=instance.id, stage_id=stage.id, attempt=instance.attempt
        )
        if row.action in {"approve", "approve_with_comments"}
    }
    return [name(row.user_id) for row in _reviewers(db, stage.id) if row.user_id not in done]


def _client_transmittal(db, revision):
    return (
        db.query(Transmittal)
        .join(TransmittalItem, TransmittalItem.transmittal_id == Transmittal.id)
        .filter(
            TransmittalItem.revision_id == revision.id,
            Transmittal.status.in_(["Issued", "Acknowledged"]),
        )
        .order_by(Transmittal.issue_date.desc(), Transmittal.id.desc())
        .first()
    )


def _packages(db, project, revisions, released, today):
    from app.domains.construction.models import WorkPackage, WorkPackageDrawing

    by_id = {row.id: row for row in revisions}
    if not by_id:
        return []
    rows = []
    for link in db.query(WorkPackageDrawing).filter(WorkPackageDrawing.revision_id.in_(list(by_id))):
        package = db.get(WorkPackage, link.package_id)
        if not package or package.project_id != project.id or package.status in {"Cancelled", "Handed Over", "Accepted"}:
            continue
        revision = by_id[link.revision_id]
        upcoming = bool(package.planned_start and package.planned_start <= today + timedelta(days=UPCOMING_DAYS))
        rows.append(
            {
                "id": package.id,
                "code": package.code,
                "name": package.name,
                "planned_start": package.planned_start,
                "linked_revision": revision.code,
                "linked_release_state": revision.release_state,
                "withdrawn": revision.release_state == "Withdrawn",
                "blocking": upcoming and revision.release_state != "Released",
                "authorized_revision": released.code if released else None,
            }
        )
    return rows


def _row(db, project, drawing, revisions, current, released, setting, name, today):
    discipline = db.get(Discipline, drawing.discipline_id)
    area = db.get(Area, drawing.area_id) if drawing.area_id else None
    revision_ids = [row.id for row in revisions]
    comments = (
        db.query(DrawingComment)
        .filter(DrawingComment.revision_id.in_(revision_ids), DrawingComment.status != "Closed")
        .all()
        if revision_ids
        else []
    )
    bucket = bucket_for(drawing, current)
    state = current.review_state if current else ""
    outcome = current.client_outcome if current else ""
    responsible = name(drawing.responsible_user_id) or "Unassigned engineer"
    metrics = {"total"}
    if bucket == "to_prepare":
        metrics.add("to_prepare")
    elif not current or state == "Not Submitted":
        metrics.add("preparing")
    if state == "Internal Review":
        metrics.add("internal_review")
    if state == "Client Review":
        metrics.add("client_review")
    if comments:
        metrics.add("open_comments")
    if state in {"Returned", "Rejected"}:
        metrics.add("returned")
    if state in {"Accepted", "Accepted with Comments"} and outcome in {"Approved", "Approved with Comments"}:
        metrics.add("approved")
    if released:
        metrics.add("released")

    allowed = {"Approved"} | ({"Approved with Comments"} if setting and setting.allow_release_with_comments else set())
    if released and current and released.id == current.id:
        release_status = "Released"
    elif released:
        release_status = "Released, newer revision in progress"
    elif (
        current
        and state in {"Accepted", "Accepted with Comments"}
        and outcome in allowed
        and current.release_state == "Not Released"
        and not any(row.revision_id == current.id and row.severity == "Blocking" for row in comments)
    ):
        release_status = "Eligible for release"
    elif any(row.release_state == "Withdrawn" for row in revisions):
        release_status = "Withdrawn"
    else:
        release_status = "Not released"

    if not current:
        overall = "Not started"
    elif state == "Rejected":
        overall = "Rejected"
    elif state == "Returned":
        overall = "Returned for correction"
    elif outcome == "Approved" and state in {"Accepted", "Accepted with Comments"}:
        overall = "Approved"
    elif outcome == "Approved with Comments" and state in {"Accepted", "Accepted with Comments"}:
        overall = "Approved with comments"
    elif state in {"Accepted", "Accepted with Comments"}:
        overall = "Internally approved, client pending"
    elif state == "Client Review":
        overall = "Awaiting client"
    elif state == "Internal Review":
        overall = "Awaiting internal review"
    else:
        overall = "Not submitted"

    pending = []
    client_party = ""
    transmittal = _client_transmittal(db, current) if current and state == "Client Review" else None
    if transmittal:
        company = db.get(Company, transmittal.recipient_company_id) if transmittal.recipient_company_id else None
        client_party = f"Client: {company.name}" if company else "Client"
    if state in {"Internal Review", "Client Review"}:
        pending += _pending_reviewers(db, current, name)
        if state == "Client Review":
            pending.append(client_party or "Client")
    elif release_status == "Eligible for release":
        pending.append("Construction release authority")
    elif state in {"Accepted", "Accepted with Comments"} and not outcome:
        pending.append(f"{responsible} (client submission)")
    elif not released or (current and released.id != current.id):
        if bucket != "released":
            pending.append(responsible)
    for comment in comments:
        owner = name(comment.owner_id)
        if owner:
            pending.append(f"{owner} (comment)")
    pending = list(dict.fromkeys(pending))

    overdue = []
    submitted_to_client = bool(current and (state == "Client Review" or outcome))
    approved = "approved" in metrics
    if (
        drawing.planned_date
        and drawing.planned_date < today
        and bucket in {"to_prepare", "in_preparation"}
        and (not current or state == "Not Submitted")
    ):
        overdue.append({"action": "Preparation", "due_date": drawing.planned_date, "pending_with": [responsible]})
    if drawing.planned_submission and drawing.planned_submission < today and not submitted_to_client and not released:
        overdue.append({"action": "Client submission", "due_date": drawing.planned_submission, "pending_with": [responsible]})
    if transmittal and transmittal.expected_response and transmittal.expected_response < today and not outcome:
        overdue.append(
            {"action": "Client response", "due_date": transmittal.expected_response, "pending_with": [client_party or "Client"]}
        )
    if drawing.planned_approval and drawing.planned_approval < today and not approved and not released:
        overdue.append({"action": "Approval", "due_date": drawing.planned_approval, "pending_with": pending or [responsible]})
    late = [row for row in comments if row.due_date and row.due_date < today]
    if late:
        owners = sorted({name(row.owner_id) or responsible for row in late})
        overdue.append(
            {
                "action": f"Comment response ({len(late)})",
                "due_date": min(row.due_date for row in late),
                "pending_with": owners,
            }
        )
    for item in overdue:
        item["days"] = (today - item["due_date"]).days

    packages = _packages(db, project, revisions, released, today)
    required, required_for = None, ""
    if bucket in {"to_prepare", "in_preparation"} and drawing.planned_date:
        required, required_for = drawing.planned_date, "Preparation"
    elif not submitted_to_client and not released and drawing.planned_submission:
        required, required_for = drawing.planned_submission, "Client submission"
    elif not approved and not released and drawing.planned_approval:
        required, required_for = drawing.planned_approval, "Approval"
    elif not released:
        starts = [row for row in packages if row["planned_start"]]
        if starts:
            first = min(starts, key=lambda row: row["planned_start"])
            required, required_for = first["planned_start"], f"Release for {first['code']}"

    last = _aware(drawing.created_at)
    event = (
        db.query(RevisionEvent.created_at)
        .filter_by(drawing_id=drawing.id)
        .order_by(RevisionEvent.created_at.desc())
        .first()
    )
    if event and event[0] and (not last or _aware(event[0]) > last):
        last = _aware(event[0])

    if overdue:
        metrics.add("overdue")
    return {
        "id": drawing.id,
        "number": drawing.number,
        "title": drawing.title,
        "discipline_id": drawing.discipline_id,
        "discipline": discipline.name if discipline else "",
        "drawing_type": drawing.drawing_type or "",
        "area_id": drawing.area_id,
        "area": f"{area.code} · {area.name}" if area else "",
        "responsible_user_id": drawing.responsible_user_id,
        "responsible": name(drawing.responsible_user_id),
        "current_revision": current.code if current else None,
        "current_revision_id": current.id if current else None,
        "preparation_status": _preparation_label(drawing),
        "internal_status": _internal_label(current),
        "client_status": _client_label(current),
        "open_comments": len(comments),
        "client_comments": sum(1 for row in comments if row.stage == "Client"),
        "overall_status": overall,
        "released_revision": released.code if released else None,
        "released_revision_id": released.id if released else None,
        "release_status": release_status,
        "planned_date": drawing.planned_date,
        "required_date": required,
        "required_for": required_for,
        "pending_with": pending,
        "overdue": overdue,
        "days_overdue": max((item["days"] for item in overdue), default=0),
        "last_updated": last,
        "lifecycle": bucket,
        "metrics": sorted(metrics),
        "work_packages": packages,
        "source": drawing.provenance or "manual",
        "record_status": drawing.record_status,
    }


def tracking(db, project, drawing, revisions, current, released, setting, today=None):
    row = _row(db, project, drawing, revisions, current, released, setting, _names(db), today or date.today())
    keys = (
        "area", "current_revision", "released_revision", "release_status", "overall_status",
        "preparation_status", "internal_status", "client_status", "open_comments", "client_comments",
        "required_date", "required_for", "pending_with", "overdue", "days_overdue", "last_updated",
        "lifecycle", "work_packages", "planned_date",
    )
    data = {key: row[key] for key in keys}
    data["lifecycle_label"] = BUCKET_LABELS[row["lifecycle"]]
    data["planned_submission"] = drawing.planned_submission
    data["planned_approval"] = drawing.planned_approval
    data["attention"] = _attention(row)
    return data


def _attention(row):
    items = []
    packages = ", ".join(item["code"] for item in row["work_packages"]) or ""
    base = {
        "drawing_id": row["id"],
        "number": row["number"],
        "discipline": row["discipline"],
        "work_packages": packages,
    }
    for item in row["overdue"]:
        items.append(
            {
                **base,
                "issue": f"{item['action']} overdue by {item['days']} day{'s' if item['days'] != 1 else ''}",
                "severity": "overdue",
                "pending_with": ", ".join(item["pending_with"]),
                "due_date": item["due_date"],
                "tab": "Reviews & Comments" if item["action"].startswith("Comment") or item["action"].startswith("Client") else "Overview",
            }
        )
    if row["internal_status"] in {"Rejected", "Changes Required"}:
        items.append(
            {
                **base,
                "issue": f"Rev {row['current_revision']} {'rejected' if row['internal_status'] == 'Rejected' else 'returned for correction'}",
                "severity": "action",
                "pending_with": row["responsible"] or "Unassigned engineer",
                "due_date": None,
                "tab": "Revisions & Files",
            }
        )
    if row["client_comments"]:
        items.append(
            {
                **base,
                "issue": f"{row['client_comments']} client comment{'s' if row['client_comments'] != 1 else ''} need action",
                "severity": "action",
                "pending_with": ", ".join(p for p in row["pending_with"] if p.endswith("(comment)")) or row["responsible"],
                "due_date": None,
                "tab": "Reviews & Comments",
            }
        )
    withdrawn = [item for item in row["work_packages"] if item["withdrawn"]]
    if withdrawn:
        items.append(
            {
                **base,
                "issue": "Release withdrawn; linked work packages need review",
                "severity": "overdue",
                "pending_with": "Construction package owners",
                "due_date": None,
                "work_packages": ", ".join(item["code"] for item in withdrawn),
                "tab": "Construction Release",
            }
        )
    blocking = [item for item in row["work_packages"] if item["blocking"] and not item["withdrawn"]]
    if blocking:
        first = min((item["planned_start"] for item in blocking if item["planned_start"]), default=None)
        items.append(
            {
                **base,
                "issue": "Not released for an upcoming work package",
                "severity": "action",
                "pending_with": ", ".join(row["pending_with"]) or row["responsible"],
                "due_date": first,
                "work_packages": ", ".join(item["code"] for item in blocking),
                "tab": "Construction Release",
            }
        )
    return items


def _counts(rows):
    counts = {key: 0 for key in METRIC_KEYS}
    comment_items = 0
    for row in rows:
        for key in row["metrics"]:
            counts[key] += 1
        comment_items += row["open_comments"]
    counts["open_comment_items"] = comment_items
    return counts


def snapshot(db, user, project, filters, today=None):
    today = today or date.today()
    names = _names(db)
    setting = db.get(EngineeringSetting, project.id)
    unreleased_ok = sees_unreleased(db, user, project)
    disciplines = accessible_disciplines(db, user, project)
    allowed = {row["id"] for row in disciplines}

    query = db.query(Drawing).filter_by(project_id=project.id)
    status = filters.get("record_status") or "Active"
    if status != "All":
        query = query.filter_by(record_status=status)
    rows = []
    for drawing in query.order_by(Drawing.number).all():
        if drawing.discipline_id not in allowed:
            continue
        revisions = (
            db.query(DrawingRevision)
            .filter_by(drawing_id=drawing.id)
            .order_by(DrawingRevision.sequence)
            .all()
        )
        released = next((row for row in reversed(revisions) if row.release_state == "Released"), None)
        if unreleased_ok:
            current = revisions[-1] if revisions else None
        else:
            if not released:
                continue
            revisions = [row for row in revisions if row.release_state in {"Released", "Superseded", "Withdrawn"}]
            current = released
        rows.append(_row(db, project, drawing, revisions, current, released, setting, names, today))

    options = {
        "disciplines": disciplines,
        "areas": sorted({(r["area_id"], r["area"]) for r in rows if r["area_id"]}, key=lambda x: x[1]),
        "drawing_types": sorted({r["drawing_type"] for r in rows if r["drawing_type"]}),
        "engineers": sorted(
            {(r["responsible_user_id"], r["responsible"]) for r in rows if r["responsible_user_id"]},
            key=lambda x: x[1],
        ),
        "internal_statuses": sorted({r["internal_status"] for r in rows}),
        "client_statuses": sorted({r["client_status"] for r in rows}),
        "release_statuses": list(RELEASE_STATUSES),
    }
    options["areas"] = [{"id": i, "name": n} for i, n in options["areas"]]
    options["engineers"] = [{"id": i, "name": n} for i, n in options["engineers"]]

    rows = [row for row in rows if _matches(row, filters)]

    missing = {
        "planned_preparation_date": sum(
            1 for r in rows if r["lifecycle"] in {"to_prepare", "in_preparation"} and not r["planned_date"]
        ),
        "responsible_engineer": sum(1 for r in rows if not r["responsible_user_id"]),
    }
    unavailable = [
        {
            "metric": "Internal review overdue",
            "reason": "Approval stages have no due date, so internal review lateness cannot be measured. Reviews still appear under Pending With.",
        }
    ]
    if missing["planned_preparation_date"]:
        unavailable.append(
            {
                "metric": "Preparation overdue",
                "reason": f"{missing['planned_preparation_date']} drawing(s) still in preparation have no planned preparation date and are not checked for lateness.",
            }
        )

    discipline_rows = []
    for item in disciplines:
        if filters.get("discipline_id") and item["id"] != filters["discipline_id"]:
            continue
        own = [row for row in rows if row["discipline_id"] == item["id"]]
        discipline_rows.append({**item, **_counts(own)})

    lifecycle = [
        {"key": key, "label": BUCKET_LABELS[key], "count": sum(1 for row in rows if row["lifecycle"] == key)}
        for key in BUCKETS
    ]
    attention = []
    for row in rows:
        attention += _attention(row)
    attention.sort(key=lambda item: (item["severity"] != "overdue", item["due_date"] or date.max, item["number"]))

    return {
        "project": {"id": project.id, "code": project.code, "name": project.name},
        "as_of": datetime.now(timezone.utc),
        "today": today,
        "released_only": not unreleased_ok,
        "metrics": [{"key": key, "label": label, "definition": text} for key, label, text in METRICS],
        "options": options,
        "totals": _counts(rows),
        "disciplines": discipline_rows,
        "lifecycle": lifecycle,
        "attention": attention,
        "unavailable": unavailable,
        "rows": rows,
    }


def _matches(row, filters):
    if filters.get("discipline_id") and row["discipline_id"] != filters["discipline_id"]:
        return False
    if filters.get("area_id") and row["area_id"] != filters["area_id"]:
        return False
    if filters.get("drawing_type") and row["drawing_type"] != filters["drawing_type"]:
        return False
    if filters.get("engineer_id") and row["responsible_user_id"] != filters["engineer_id"]:
        return False
    if filters.get("internal_status") and row["internal_status"] != filters["internal_status"]:
        return False
    if filters.get("client_status") and row["client_status"] != filters["client_status"]:
        return False
    if filters.get("release_status") and row["release_status"] != filters["release_status"]:
        return False
    if filters.get("required_from") and (not row["required_date"] or row["required_date"] < filters["required_from"]):
        return False
    if filters.get("required_to") and (not row["required_date"] or row["required_date"] > filters["required_to"]):
        return False
    if filters.get("overdue_only") and not row["overdue"]:
        return False
    text = (filters.get("q") or "").strip().lower()
    if text and text not in row["number"].lower() and text not in row["title"].lower():
        return False
    return True


def drill(rows, metric="", discipline_id=None):
    if metric and metric not in METRIC_KEYS:
        raise HTTPException(422, "Unknown metric")
    picked = rows
    if discipline_id:
        picked = [row for row in picked if row["discipline_id"] == discipline_id]
    if metric:
        picked = [row for row in picked if metric in row["metrics"]]
    return picked


def page(data, metric="", drill_discipline=None, sort="number", direction="asc", page_no=1, size=25):
    if sort not in SORTS:
        raise HTTPException(422, "Unknown sort column")
    size = max(5, min(size, 100))
    picked = drill(data["rows"], metric, drill_discipline)
    picked = sorted(picked, key=SORTS[sort], reverse=direction == "desc")
    total = len(picked)
    pages = max(1, (total + size - 1) // size)
    page_no = max(1, min(page_no, pages))
    start = (page_no - 1) * size
    data = {key: value for key, value in data.items() if key != "rows"}
    data["register"] = {
        "items": picked[start : start + size],
        "total": total,
        "page": page_no,
        "pages": pages,
        "size": size,
        "metric": metric,
        "discipline_id": drill_discipline,
        "sort": sort,
        "direction": direction,
    }
    return data


def export(data, metric="", drill_discipline=None):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "Drawing Number", "Title", "Discipline", "Drawing Type", "Unit/Area/Block", "Current Revision",
            "Preparation Status", "Internal Review Status", "Client Review Status", "Open Comments",
            "Overall Approval Status", "Released Revision", "Construction Release Status", "Required Date",
            "Required For", "Pending With", "Overdue Actions", "Days Overdue", "Last Updated",
        ]
    )
    for row in sorted(drill(data["rows"], metric, drill_discipline), key=SORTS["number"]):
        writer.writerow(
            [
                row["number"], row["title"], row["discipline"], row["drawing_type"], row["area"],
                row["current_revision"] or "", row["preparation_status"], row["internal_status"],
                row["client_status"], row["open_comments"], row["overall_status"], row["released_revision"] or "",
                row["release_status"], row["required_date"] or "", row["required_for"], "; ".join(row["pending_with"]),
                "; ".join(f"{item['action']} due {item['due_date']}" for item in row["overdue"]), row["days_overdue"],
                row["last_updated"].isoformat() if row["last_updated"] else "",
            ]
        )
    return out.getvalue()
