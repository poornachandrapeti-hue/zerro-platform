from app.domains.commercial_financials.movement_journal_evidence import validate_journal_evidence


def posting(**kw):
    e = dict(posting_id='J-1', status='POSTED', organization_id=1, project_id=2,
             stock_movement_id=3, currency='INR', posted_at='2026-10-01T10:00:00Z',
             posted_by=7, total_debit='100.00', total_credit='100.00')
    e.update(kw)
    return e


def check(entries=None, **kw):
    opts = dict(organization_id=1, project_id=2, movement_id=3,
                currency='INR', movement_amount='100.00',
                entries=[posting()] if entries is None else entries,
                finance_source_verified=True)
    opts.update(kw)
    return validate_journal_evidence(**opts)


def test_complete_evidence_still_uncertified():
    result = check()
    assert result['status'] == 'EVIDENCE_CONSISTENT_NOT_CERTIFIED'
    assert result['journal_posting_verified'] is False


def test_untrusted_source_blocked():
    assert 'FINANCE_SOURCE_NOT_AUTHENTICATED' in check(finance_source_verified=False)['issues']


def test_duplicate_postings_blocked():
    assert 'EXPECTED_ONE_AUTHORITATIVE_POSTING' in check(entries=[posting(), posting(posting_id='J-2')])['issues']


def test_missing_posting_blocked():
    assert check(entries=[])['status'] == 'BLOCKED'


def test_wrong_project_blocked():
    assert 'JOURNAL_SCOPE_MISMATCH' in check(entries=[posting(project_id=99)])['issues']


def test_wrong_movement_blocked():
    assert 'JOURNAL_MOVEMENT_MISMATCH' in check(entries=[posting(stock_movement_id=4)])['issues']


def test_unposted_blocked():
    assert 'JOURNAL_NOT_POSTED' in check(entries=[posting(status='DRAFT')])['issues']


def test_unbalanced_blocked():
    assert 'UNBALANCED_JOURNAL' in check(entries=[posting(total_credit='99')])['issues']


def test_amount_mismatch_blocked():
    assert 'JOURNAL_AMOUNT_MISMATCH' in check(entries=[posting(total_debit='110', total_credit='110')])['issues']


def test_invalid_nan_amount_blocked():
    assert 'INVALID_JOURNAL_AMOUNT' in check(entries=[posting(total_debit='NaN')])['issues']


def test_missing_audit_blocked():
    assert 'MISSING_POSTING_AUDIT' in check(entries=[posting(posted_by=None)])['issues']


def test_currency_mismatch_blocked():
    assert 'JOURNAL_CURRENCY_MISMATCH' in check(entries=[posting(currency='USD')])['issues']
