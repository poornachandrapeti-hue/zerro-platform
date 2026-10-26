import json
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.baseline_comparison import load_approved_manifest, apply_baseline


def test_approved_baseline_and_scoped_alert(tmp_path):
    f = tmp_path/'baseline.json'
    f.write_text(json.dumps({'project_code':'STEEL-001','approval_status':'approved','approval_reference':'PMC-APP-01','approved_by':'Planning Manager','approved_on':'2026-09-01','revision':'R1','activities':[{'package_code':'WP-CIV-01','activity_code':'ACT-01','unit':'m3','scope_quantity':100,'cumulative_plan':[{'date':'2026-09-01','quantity':0},{'date':'2026-10-01','quantity':70},{'date':'2026-11-01','quantity':100}]}]}))
    manifest = load_approved_manifest(str(f),'STEEL-001')
    packages = [{'package_code':'WP-CIV-01','discipline_name':'Civil','activities':[{'activity_code':'ACT-01','scope_quantity':100,'verified_quantity':55,'unit':'m3'}]}]
    alerts,status = apply_baseline(packages,manifest,date(2026,10,18),10)
    assert status == 'approved_revision'
    assert packages[0]['activities'][0]['variance_pp'] == -15
    assert len(alerts) == 1
    packages[0]['activities'][0]['unit'] = 'MT'
    alerts,_=apply_baseline(packages,manifest,date(2026,10,18),10)
    assert alerts == []
    assert packages[0]['activities'][0]['baseline_status'] == 'scope_or_unit_mismatch'


def test_unapproved_denied(tmp_path):
    f = tmp_path/'bad.json'
    f.write_text(json.dumps({'project_code':'STEEL-001','approval_status':'draft','activities':[]}))
    try:
        load_approved_manifest(str(f),'STEEL-001')
    except ValueError:
        return
    assert False, 'Draft baseline should not be accepted'
