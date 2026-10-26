"""Read-only, fail-closed source diagnostics for Contracts closeout.

Project-level quality blockers are informative and conservative: a project-wide
hold may affect more than one contract. An empty result does NOT grant QA
acceptance or satisfy the contract-specific QA closeout gate.
"""
from sqlalchemy.orm import Session
from app.domains.quality.models import QualityHold, QualityPunch, Nonconformance


def quality_blockers(db: Session, organization_id: int, project_id: int) -> dict:
    """Return source-linked unresolved QA blockers for a scoped project.

    In particular, do not confuse 'no blockers found' with QA acceptance.
    DB failures must propagate instead of reporting an empty / passing result.
    """
    holds = db.query(QualityHold).filter_by(
        organization_id=organization_id, project_id=project_id
    ).filter(QualityHold.blocks_handover.is_(True)).filter(
        QualityHold.status != 'Released'
    ).all()
    punches = db.query(QualityPunch).filter_by(
        organization_id=organization_id, project_id=project_id,
        blocking=True
    ).filter(~QualityPunch.status.in_(['Closed', 'Cancelled'])).all()
    ncrs = db.query(Nonconformance).filter_by(
        organization_id=organization_id, project_id=project_id
    ).filter(~Nonconformance.status.in_(['Closed', 'Cancelled'])).all()
    blockers = (
        [{'source': 'quality_holds', 'id': x.id, 'status': x.status} for x in holds]
        + [{'source': 'quality_punches', 'id': x.id, 'status': x.status} for x in punches]
        + [{'source': 'quality_ncrs', 'id': x.id, 'status': x.status} for x in ncrs]
    )
    return {
        'source_system': 'Quality', 'organization_id': organization_id,
        'project_id': project_id, 'scope': 'project', 'blockers': blockers,
        'blocker_count': len(blockers),
        'acceptance_verified': False,
        'reason': 'Project-wide blockers are diagnostics only; contract-scoped QA acceptance must be independently verified',
    }
