"""Phase 5 read-only, service-authenticated progress export. Never serves draft figures as verified."""
import hmac
from datetime import datetime, timezone, date
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from .db import get_db
from .config import settings
from .domains.identity_projects.models import Project, Discipline
from .domains.construction.models import WorkPackage, ConstructionActivity
from .domains.construction.progress import activity_measures

router = APIRouter(prefix="/api/integration/vision360", tags=["Vision360 integration"])

@router.get("/projects/{project_code}/verified-progress")
def verified_progress(project_code: str, x_vision_service_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    secret = settings.vision360_service_key
    if not secret or not x_vision_service_key or not hmac.compare_digest(x_vision_service_key, secret):
        raise HTTPException(403, "Integration unavailable")
    org = settings.vision360_organization_id
    if not org:
        raise HTTPException(503, "Integration organization not configured")
    project = db.query(Project).filter(Project.organization_id == org, Project.code == project_code).one_or_none()
    if project is None:
        raise HTTPException(404, "Project not found")
    packages = db.query(WorkPackage).filter(WorkPackage.project_id == project.id, WorkPackage.organization_id == org, WorkPackage.status != "Cancelled").order_by(WorkPackage.id).all()
    # Bounded pull: refuse incomplete totals instead of silently cutting off work packages.
    if len(packages) > 500:
        raise HTTPException(503, "Project exceeds integration page limit")
    activities = db.query(ConstructionActivity).filter(ConstructionActivity.project_id == project.id, ConstructionActivity.organization_id == org, ConstructionActivity.active == True).order_by(ConstructionActivity.id).all()
    if len(activities) > 2000:
        raise HTTPException(503, "Project exceeds integration activity limit")
    grouped = {}
    for a in activities:
        grouped.setdefault(a.package_id, []).append(a)
    disciplines = {d.id: d.name for d in db.query(Discipline).all()}
    rows = []
    for p in packages:
        measures = []
        for a in grouped.get(p.id, []):
            v = activity_measures(db, a)
            measures.append({"activity_id": a.id, "activity_code": a.code, "method": a.measurement_method,
                 "scope_quantity": v["scope_quantity"], "verified_quantity": v["verified_quantity"],
                 "verified_percent": v["verified_percent"], "unit": v["unit"]})
        rows.append({"package_id":p.id, "package_code":p.code, "name":p.name, "status":p.status,
            "discipline_id":p.discipline_id, "discipline_name":disciplines.get(p.discipline_id, ""),
            "planned_start":p.planned_start.isoformat() if p.planned_start else None,
            "planned_finish":p.planned_finish.isoformat() if p.planned_finish else None, "activities":measures})
    return {"source":"siteforge", "project_code":project.code, "generated_at":datetime.now(timezone.utc).isoformat(),
        "measurement":"approved progress reports only; quality acceptance and billing separate", "packages":rows}


@router.get("/projects/{project_code}/planning-monitor")
def planning_monitor(project_code: str, x_vision_service_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Full-project reporting only. Never exports drafts or per-person planning records."""
    from collections import defaultdict
    from decimal import Decimal
    from .domains.planning_reporting.workspace_models import (PlanningPublication, PlanningPeriodTarget,
        PlanningProgressCapture, PlanningAlert, PlanningMilestoneEvidence)
    secret = settings.vision360_service_key
    if not secret or not x_vision_service_key or not hmac.compare_digest(secret, x_vision_service_key):
        raise HTTPException(403, "Integration unavailable")
    org = settings.vision360_organization_id
    if not org:
        raise HTTPException(503, "Integration organization not configured")
    project = db.query(Project).filter_by(organization_id=org, code=project_code).one_or_none()
    if project is None:
        raise HTTPException(404, "Project not found")
    current = db.query(PlanningPublication).filter_by(organization_id=org, project_id=project.id,
        status="Approved", is_current=True).order_by(PlanningPublication.id.desc()).limit(2).all()
    if len(current) > 1:
        raise HTTPException(409, "Ambiguous current approved schedule publication")
    plan = []
    observed = []
    revision = None
    if current:
        pub = current[0]
        revision = pub.revision
        targets = db.query(PlanningPeriodTarget).filter_by(organization_id=org, project_id=project.id,
            publication_id=pub.id).order_by(PlanningPeriodTarget.period_end, PlanningPeriodTarget.id).limit(10002).all()
        if len(targets) > 10000:
            raise HTTPException(503, "Planning target export limit reached")
        if targets:
            by_activity = defaultdict(list)
            for t in targets:
                by_activity[t.activity_id].append(t)
            weights = {aid: rows[0].weight_basis_points for aid, rows in by_activity.items()}
            if (sum(weights.values()) != 10000 or
                any(any(t.weight_basis_points != weights[aid] for t in rows) for aid, rows in by_activity.items())):
                raise HTTPException(409, "Incomplete or inconsistent approved planning weights")
            dates = sorted({t.period_end for t in targets})
            for day in dates:
                total = Decimal(0)
                for aid, rows in by_activity.items():
                    applicable = [r.cumulative_percent for r in rows if r.period_end <= day]
                    total += Decimal(weights[aid]) * Decimal(applicable[-1] if applicable else 0)
                plan.append({"date": day.isoformat(), "planned_percent": float(total / 10000)})
        captures = db.query(PlanningProgressCapture).filter_by(organization_id=org, project_id=project.id,
            publication_id=pub.id).order_by(PlanningProgressCapture.captured_at).limit(1001).all()
        if len(captures) > 1000:
            raise HTTPException(503, "Progress capture export limit reached")
        observed = [{"date": c.captured_at.isoformat(), "verified_percent": (c.snapshot or {}).get("verified_percent")}
                    for c in captures]
    milestones = []
    critical_activities = []
    calculation_info = {"status": "no_approved_publication"}
    if current:
        # Read frozen, approved publication ONLY; never recompute a draft as if it were published.
        snap = current[0].snapshot or {}
        calc = snap.get("calculation") or {}
        rows = calc.get("activities") or []
        frozen = {a.get("id"): a for a in (snap.get("activities") or []) if isinstance(a, dict)}
        if isinstance(rows, list) and len(rows) <= 5000 and calc.get("calculation_basis") == "DRAFT_CPM_WORKING_HOURS_V1":
            for item in rows:
                if not isinstance(item, dict):
                    continue
                detail = frozen.get(item.get("id"), {})
                result = {"activity_code": str(item.get("code") or "")[:80],
                    "activity_name": str(item.get("name") or "")[:240],
                    "baseline_start": item.get("start"), "baseline_finish": item.get("finish"),
                    "total_float_hours": item.get("total_float_hours"),
                    "critical": item.get("critical") is True}
                if item.get("activity_type") == "Milestone":
                    # No verified achievement source is embedded in this frozen baseline.
                    milestones.append({**result, "actual_finish": None, "variance_days": None,
                        "variance_status": "actual_not_available"})
                if item.get("critical") is True and item.get("activity_type") != "Summary":
                    critical_activities.append(result)
            calculation_info = {"status":"approved_snapshot","basis":calc.get("calculation_basis"),
                "note":"Critical flags and total float were frozen at approval, not live current criticality."}
        else:
            calculation_info = {"status":"unsupported_or_missing_approved_calculation"}
    # Phase 11: live VERIFIED completion status for explicitly source-linked milestones.
    # The report date on a later report is not proof of the first completion date, so
    # neither actual_finish nor contractual variance is synthesized.
    if milestones:
        milestone_snapshots = {a.get("id"):a for a in (current[0].snapshot or {}).get("activities", []) if isinstance(a, dict)}
        id_by_code = {str(a.get("code")):a for a in milestone_snapshots.values()}
        candidate_ids = set()
        mapping = {}
        duplicates = set()
        for m in milestones:
            frozen_row = id_by_code.get(m["activity_code"], {})
            typ = str(frozen_row.get("source_type") or "").lower().strip()
            raw_id = str(frozen_row.get("source_id") or "")
            m["completion_status"] = "unmapped"
            m["verified_percent"] = None
            if typ in ("construction_activity", "construction.activity") and raw_id.isdecimal():
                sid = int(raw_id)
                if sid in mapping: duplicates.add(sid)
                mapping[sid] = m
                candidate_ids.add(sid)
            elif typ or raw_id:
                m["completion_status"] = "unsupported_source"
        if len(candidate_ids) > 500:
            raise HTTPException(503, "Milestone source lookup limit reached")
        if candidate_ids:
            linked = db.query(ConstructionActivity,WorkPackage).join(WorkPackage,WorkPackage.id==ConstructionActivity.package_id).filter(
                ConstructionActivity.id.in_(candidate_ids), ConstructionActivity.organization_id==org,
                ConstructionActivity.project_id==project.id, ConstructionActivity.active==True,
                WorkPackage.project_id==project.id, WorkPackage.organization_id==org,
                WorkPackage.status!="Cancelled").all()
            for act, package in linked:
                m = mapping[act.id]
                source = id_by_code.get(m["activity_code"], {})
                if act.id in duplicates:
                    m["completion_status"] = "duplicate_source_mapping"
                elif (source.get("company_id") != act.company_id or
                      (source.get("discipline_id") is not None and source.get("discipline_id") != package.discipline_id)):
                    m["completion_status"] = "source_scope_mismatch"
                else:
                    measured = activity_measures(db,act)
                    try:
                        percent = float(measured["verified_percent"])
                    except (TypeError,ValueError,KeyError):
                        m["completion_status"] = "measurement_unavailable"
                    else:
                        m["verified_percent"] = percent
                        m["completion_status"] = "verified_complete" if percent >= 100 else "incomplete"
                        m["verification_source"] = "construction_approved_progress"
                        # A comparison is only a risk indicator, not proven milestone variance.
                        due = m.get("baseline_finish")
                        if m["completion_status"] == "incomplete" and due:
                            try:
                                m["monitoring_status"] = "past_baseline_date_unverified" if date.fromisoformat(str(due)[:10]) < datetime.now(timezone.utc).date() else "in_progress"
                            except ValueError:
                                m["monitoring_status"] = "baseline_date_invalid"
            for sid,m in mapping.items():
                if m["completion_status"] == "unmapped":m["completion_status"] = "source_not_found"

    # Approved achievement evidence is distinct from verified quantity percentages.
    # Never turn a percentage or a capture timestamp into a completion date.
    if milestones and current:
        evidence_rows = db.query(PlanningMilestoneEvidence).filter_by(
            organization_id=org,project_id=project.id,publication_id=current[0].id,status='Approved').limit(501).all()
        if len(evidence_rows)>500:
            raise HTTPException(503,'Milestone evidence export limit reached')
        evidence_by_code = {e.activity_code:e for e in evidence_rows}
        for m in milestones:
            e=evidence_by_code.get(m['activity_code'])
            if e and m.get('completion_status') == 'verified_complete':
                m['actual_finish']=e.achieved_on.isoformat()
                due=m.get('baseline_finish')
                try:
                    m['variance_days']=(e.achieved_on-date.fromisoformat(str(due)[:10])).days if due else None
                    m['variance_status']='approved_evidence_and_verified_completion' if due else 'baseline_date_unavailable'
                except ValueError:
                    m['variance_status']='baseline_date_invalid'
            elif e:
                m['variance_status']='evidence_approved_but_execution_not_verified'

    alerts = db.query(PlanningAlert).filter_by(organization_id=org, project_id=project.id).filter(
        PlanningAlert.status.in_(["Open", "Acknowledged"])).order_by(PlanningAlert.id.desc()).limit(101).all()
    if len(alerts) > 100:
        raise HTTPException(503, "Planning alert export limit reached")
    # Avoid exporting descriptions, identities and confidential supporting records.
    counts = {}
    for a in alerts:
        counts[a.severity] = counts.get(a.severity, 0) + 1
    alert_details = [{"id": a.id, "severity": a.severity, "status": a.status,
        "trigger_type": a.trigger_type, "source_type": a.source_type,
        "first_detected_at": a.first_detected_at.isoformat() if a.first_detected_at else None,
        "last_detected_at": a.last_detected_at.isoformat() if a.last_detected_at else None}
        for a in alerts]
    from .domains.planning_reporting.forecast_models import PlanningForecastRevision
    approved_forecast = db.query(PlanningForecastRevision).filter_by(
        organization_id=org, project_id=project.id, status='Approved').order_by(
        PlanningForecastRevision.data_date.desc(), PlanningForecastRevision.id.desc()).first()
    forecast_summary = None
    if approved_forecast is not None:
        result = approved_forecast.result or {}
        from .domains.planning_reporting.forecast_reconciliation import finish_variance
        baseline_finish = None
        if current and current[0].schedule_id == approved_forecast.schedule_id:
            calc = (current[0].snapshot or {}).get('calculation') or {}
            dates = [v.get('finish') for v in calc.get('activities',[]) if isinstance(v,dict) and v.get('finish')]
            if calc.get('calculation_basis') == 'DRAFT_CPM_WORKING_HOURS_V1' and dates:
                baseline_finish = max(dates)
        variance = finish_variance(result.get('project_finish'), baseline_finish)
        forecast_summary = {'baseline_finish':baseline_finish, 'finish_variance_days':variance['variance_days'],
            'finish_variance_basis':variance['status'],
            'revision': approved_forecast.revision,
            'data_date': approved_forecast.data_date.isoformat(),
            'project_finish': result.get('project_finish'),
            'basis': result.get('basis'),
            'source_actuals_verified': False,
            'note': 'Approved planner forecast based on supplied assumptions; not a contractual baseline or verified actual.'}
    advanced_monitoring = None
    if current and approved_forecast is not None and current[0].schedule_id == approved_forecast.schedule_id:
        baseline_calculation = (current[0].snapshot or {}).get('calculation') or {}
        forecast_calculation = approved_forecast.result or {}
        if (baseline_calculation.get('calculation_basis') == 'DRAFT_CPM_WORKING_HOURS_V1'
                and forecast_calculation.get('calculation_basis') == 'DRAFT_CPM_WORKING_HOURS_V1'
                and isinstance(baseline_calculation.get('activities'), list)
                and isinstance(forecast_calculation.get('activities'), list)):
            from .domains.planning_reporting.advanced_monitoring import summarize
            advanced_monitoring = summarize(baseline_calculation['activities'],
                forecast_calculation['activities'], milestones,
                approved_forecast.data_date.isoformat())
    return {"source": "siteforge_planning", "project_code": project.code,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "approved_revision": revision, "planned": plan, "observed": observed, "approved_forecast": forecast_summary,
        "advanced_monitoring": advanced_monitoring,
        "active_alert_count": len(alerts), "alert_severity_counts": counts,
        "alerts_detail": alert_details, "milestones": milestones[:500],
        "critical_activities": critical_activities[:1000], "calculation_info": calculation_info,
        "note": "Whole-project figures only. Observed points are recorded captures, not a reconstruction of historical events. Missing data is not zero."}
