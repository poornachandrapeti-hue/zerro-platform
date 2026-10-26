from pathlib import Path
from app.domains.commercial_financials.journal_authority_audit import inspect_finance_models


def test_real_models_do_not_mislabel_supplier_invoice_as_gl():
    source = (Path(__file__).parents[1] / 'app/domains/commercial_financials/models.py').read_text()
    result = inspect_finance_models(source)
    assert result['status'] == 'BLOCKED'
    assert result['finance_supplier_invoice_posting_is_not_general_ledger'] is True
    assert not result['general_ledger_posting_candidates']
    assert result['journal_posting_authority_verified'] is False


def test_complete_model_is_still_unverified_without_database_readback():
    source = 'class FinanceGeneralJournal:\n    __tablename__ = "finance_general_journals"\n' + ''.join(f'    {f}: int = 1\n' for f in ('organization_id','project_id','stock_movement_id','currency','total_debit','total_credit','status','posted_at','posted_by'))
    result = inspect_finance_models(source)
    assert result['status'] == 'SOURCE_CONTRACT_PRESENT_DB_UNVERIFIED'
    assert result['journal_posting_authority_verified'] is False


def test_partial_model_must_not_count():
    result = inspect_finance_models('class FinanceJournal:\n    __tablename__="finance_journal"\n    project_id: int = 1\n')
    assert result['status'] == 'BLOCKED'
