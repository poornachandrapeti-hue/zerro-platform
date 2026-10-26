from copy import deepcopy
from app.domains.commercial_financials.gl_receipt_verification import verify_gl_receipt


def fixtures():
    handoff = {'posting_status':'NOT_POSTED','idempotency_key':'finance-proposal:1:2:3:1',
        'payload_sha256':'abc', 'journal_proposal':{'organization_id':1,'project_id':2,
        'proposal_id':3,'proposal_revision':1,'source_movement_line_id':4,
        'currency':'INR','balanced_total':'125.00'}}
    receipt = {**{k:handoff['journal_proposal'][k] for k in ('organization_id','project_id',
        'proposal_id','proposal_revision','source_movement_line_id','currency')},
        'idempotency_key':handoff['idempotency_key'],'payload_sha256':'abc',
        'status':'POSTED','posted_at':'2026-10-26T08:00:00Z','posted_by':10,
        'external_journal_id':'GL-1','total_debit':'125.00','total_credit':'125.00'}
    return handoff, receipt


def test_matching_still_not_authoritative():
    h,r=fixtures(); result=verify_gl_receipt(h,r)
    assert result['matches_handoff'] and not result['journal_posting_verified']
    assert result['authoritative_ledger_readback_required']


def test_mismatched_project():
    h,r=fixtures(); r['project_id']=9
    assert 'mismatched_project_id' in verify_gl_receipt(h,r)['reasons']


def test_mismatched_digest():
    h,r=fixtures(); r['payload_sha256']='other'
    assert 'mismatched_payload_sha256' in verify_gl_receipt(h,r)['reasons']


def test_missing_audit():
    h,r=fixtures(); r['posted_at']=None
    assert 'posting_audit_missing' in verify_gl_receipt(h,r)['reasons']


def test_total_mismatch():
    h,r=fixtures(); r['total_credit']='124.00'
    assert 'journal_totals_mismatch' in verify_gl_receipt(h,r)['reasons']


def test_nonfinite_rejected():
    h,r=fixtures(); r['total_debit']='NaN'
    assert 'journal_totals_mismatch' in verify_gl_receipt(h,r)['reasons']


def test_missing_reference():
    h,r=fixtures(); r.pop('external_journal_id')
    assert 'journal_id_missing' in verify_gl_receipt(h,r)['reasons']


def test_bad_evidence_format():
    assert not verify_gl_receipt(None, {})['matches_handoff']
