from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'frontend' / 'src'

def test_partner_return_form_uses_existing_company_scoped_api():
    source = (ROOT / 'partner' / 'PartnerMaterialReturns.tsx').read_text()
    assert '/partner/projects/${project}/stores/material-returns' in source
    assert '/partner/projects/${pid}/stores/material-returns' in source
    assert 'handover_id:Number(selected)' in source
    assert 'rows.some(r=>r.handover_id===h.id)' in source
    assert 'No inventory was posted' in source

def test_internal_receipt_and_qa_use_existing_routes():
    source = (ROOT / 'stores.tsx').read_text()
    assert 'stores/material-returns/${row.id}/${action}' in source
    assert "action==='receive'" in source
    assert "'qa-disposition'" in source
    assert 'This does not post inventory' in source

def test_partner_navigation_mounted():
    source = (ROOT / 'App.tsx').read_text()
    assert 'PartnerMaterialReturns initialProjectId={homeProject}' in source
    assert '"partner-material-returns", "Material Returns"' in source
