"""Fail-closed partner Planning scope projection.

Never expose source IDs, internal ownership notes, commercial values or
cross-company summary totals through this projection.
"""

def visible_to_membership(company_id, discipline_id, membership):
    if membership.company_id != company_id:
        return False
    if membership.scope == 'ALL':
        return True
    if membership.scope != 'SELECTED':
        return False
    return discipline_id is not None and discipline_id in (membership.discipline_ids or [])


def partner_activity_projection(activity):
    return {
        'activity_code': activity.code,
        'activity_name': activity.name,
        'activity_type': activity.activity_type,
        'planned_start': activity.planned_start,
        'planned_finish': activity.planned_finish,
        'discipline_id': activity.discipline_id,
    }
