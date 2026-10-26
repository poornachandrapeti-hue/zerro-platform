"""Idempotent, least-privilege project provisioning and header sync from SiteForge.

The project header (name, client, location, dates, budget, currency, status) mirrors
SiteForge on every load. Does not fabricate construction progress or milestones;
existing discipline records are never overwritten.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .models import Project, Discipline
from .project_identity import to_command_center_code


def _source_dates(source: dict) -> tuple[date, date] | None:
    try:
        start = date.fromisoformat(source['planned_start'])
        finish = date.fromisoformat(source['planned_finish'])
    except (KeyError, TypeError, ValueError):
        return None
    return (start, finish) if finish >= start else None


def _source_budget(source: dict) -> Decimal:
    try:
        value = Decimal(str(source.get('contract_value') or '0'))
    except InvalidOperation:
        return Decimal('0')
    return value if value.is_finite() and value >= 0 else Decimal('0')


def _apply_header(project: Project, source: dict, dates: tuple[date, date] | None) -> None:
    project.name = source['name'][:180]
    project.client = (source.get('client') or '')[:120]
    project.location = (source.get('location') or '')[:160]
    project.approved_budget = _source_budget(source)
    project.currency = (source.get('currency') or 'INR')[:8]
    project.status = (source.get('status') or 'Draft')[:30]
    if dates:
        start, finish = dates
        if project.forecast_finish is None or project.forecast_finish == project.planned_finish or project.forecast_finish < start:
            project.forecast_finish = finish
        project.start_date, project.planned_finish = start, finish


def provision_authorized_projects(db, authority: dict, allowed_codes: set[str], mapping: dict, discipline_grants: dict[str, set[str]] | None = None) -> dict:
    """Provision and sync only approved identities a signed-in user may view.

    New projects need valid planned dates; existing ones keep their dates if the
    source dates are missing or invalid. No destructive reconciliation.
    """
    stats = {"created": 0, "skipped_missing_dates": 0, "synced": 0}
    existing = {p.code: p for p in db.scalars(select(Project)).all()}
    discipline_grants = discipline_grants or {}
    for source_code, source in authority.items():
        cc_code = to_command_center_code(source_code, mapping)
        if cc_code not in allowed_codes:
            continue
        dates = _source_dates(source)
        if cc_code in existing:
            _apply_header(existing[cc_code], source, dates)
            stats['synced'] += 1
            continue
        if dates is None:
            stats['skipped_missing_dates'] += 1
            continue
        start, finish = dates
        project = Project(code=cc_code, start_date=start, planned_finish=finish, forecast_finish=finish)
        _apply_header(project, source, dates)
        try:
            # Savepoint handles concurrent requests provisioning the same code.
            with db.begin_nested():
                db.add(project)
                db.flush()
                # Empty, zero-weight discipline shells are navigation containers,
                # not evidence of work completed or verified project progress.
                for code in sorted(discipline_grants.get(cc_code, set())):
                    if not code or len(code) > 30:
                        continue
                    db.add(Discipline(
                        project_id=project.id, code=code, name=code.title(),
                        weight=Decimal('0'), planned_progress=Decimal('0'),
                        actual_progress=Decimal('0'), budget=Decimal('0'),
                        target_date=finish,
                    ))
                db.flush()
            stats['created'] += 1
            existing[cc_code] = project
        except IntegrityError:
            stats['synced'] += 1
    db.commit()
    return stats
