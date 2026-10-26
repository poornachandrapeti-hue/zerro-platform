"""Evidence summaries for Planning resource checks; not shift-level availability approvals."""
from datetime import date


def capacity_evidence(demands, *, as_of: date):
    """Do not treat a free-text reference as verified operational capacity."""
    result=[]
    for d in demands:
        active=d.period_start <= as_of <= d.period_end
        supplied=d.confirmed_capacity is not None and bool((d.capacity_source or '').strip())
        result.append({
            'demand_id':d.id,'activity_id':d.activity_id,
            'resource_type':d.resource_type,'resource_name':d.resource_name,
            'period_start':d.period_start.isoformat(),'period_end':d.period_end.isoformat(),
            'demand_quantity':d.demand_quantity,'demand_unit':d.demand_unit,
            'planning_capacity_value':d.confirmed_capacity if supplied else None,
            'planning_capacity_reference':d.capacity_source if supplied else None,
            'capacity_evidence_status':'planner-referenced-unverified' if supplied else 'missing',
            'covers_data_date':active,
            'available_for_automatic_scheduling':False,
        })
    return result


def mobilization_summary(deployments, *, as_of:date):
    """Count mobilized deployments, without asserting presence, eligibility or shift availability."""
    counts={}
    for d in deployments:
        if d.status != 'Mobilized' or (d.actual_start and d.actual_start>as_of) or (d.actual_end and d.actual_end<as_of):
            continue
        key=(d.company_id,d.discipline_id)
        counts.setdefault(key,set()).add(d.personnel_id)
    return [{'company_id':company,'discipline_id':discipline,'mobilized_personnel_count':len(people),
             'capacity_status':'indicative-mobilization-only'}
            for (company,discipline),people in sorted(counts.items(),key=lambda x:(x[0][0] or 0,x[0][1] or 0))]
