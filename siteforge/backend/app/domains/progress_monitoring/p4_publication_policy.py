"""P4 approval/publication policy decisions ONLY: no DB writes, endpoints or finance effects.

Call from authenticated server code with authoritative actor identity and measured source facts.
"""
from dataclasses import dataclass

class PublicationPolicyError(ValueError):
    pass

@dataclass(frozen=True)
class PublicationDecision:
    next_state:str
    next_version:int
    event:str
    published:bool

ALLOWED={'Draft':{'submit':'Pending'},'Pending':{'approve':'Approved','reject':'Rejected'},
         'Rejected':{'revise':'Draft'},'Approved':{'publish':'Published'},
         'Published':{'supersede':'Superseded'},'Superseded':{}}

def decide(*, state, action, version, expected_version, proposer_id, actor_id,
           permissions, source_integrity, wbs_complete, approvals_current, project_authorized,
           revision_reason=None):
    if type(version) is not int or type(expected_version) is not int or version<1 or version!=expected_version:
        raise PublicationPolicyError('Stale or invalid version')
    if project_authorized is not True:raise PublicationPolicyError('Project authorization missing')
    next_state=ALLOWED.get(state,{}).get(action)
    if next_state is None:raise PublicationPolicyError('Invalid state transition')
    needed={'submit':'progress.submit','approve':'progress.approve','reject':'progress.approve',
            'revise':'progress.revise','publish':'progress.publish','supersede':'progress.publish'}[action]
    if not isinstance(permissions,(set,frozenset)) or needed not in permissions:
        raise PublicationPolicyError('Permission denied')
    if action in ('approve','reject','publish') and (not actor_id or actor_id==proposer_id):
        raise PublicationPolicyError('Independent reviewer/publisher required')
    if action in ('submit','approve','publish') and (source_integrity is not True or wbs_complete is not True or approvals_current is not True):
        raise PublicationPolicyError('Source evidence or approvals incomplete')
    if action in ('revise','supersede') and (not isinstance(revision_reason,str) or not revision_reason.strip()):
        raise PublicationPolicyError('Revision reason required')
    return PublicationDecision(next_state,next_version=version+1,event=action,published=next_state=='Published')
