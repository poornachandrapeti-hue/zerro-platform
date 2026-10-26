#!/usr/bin/env python3
"""Non-destructive ZerroBuild Progress release gate. Run in staging before production."""
import ast, collections, pathlib, subprocess, sys, json
ROOT=pathlib.Path(__file__).resolve().parents[1]
BACKEND=ROOT/'backend'; FRONTEND=ROOT/'frontend'
def run(title, cmd, cwd, timeout=120):
    print('\n== '+title+' ==',flush=True)
    try:
        p=subprocess.run(cmd,cwd=cwd,timeout=timeout,check=False)
        print(title+':', 'PASS' if p.returncode==0 else 'FAIL',flush=True)
        return p.returncode==0
    except (OSError,subprocess.TimeoutExpired) as exc:
        print(title+': NOT VERIFIED ('+str(exc)+')',flush=True);return False

def migrations():
    folder=BACKEND/'migrations'/'versions'; rows=[]; seen=set(); referenced=set(); errors=[]
    for f in folder.glob('*.py'):
        d={}
        try:
            tree=ast.parse(f.read_text(encoding='utf-8'))
            for node in tree.body:
                if isinstance(node,ast.Assign):
                    for t in node.targets:
                        if isinstance(t,ast.Name) and t.id in ('revision','down_revision'):
                            try:d[t.id]=ast.literal_eval(node.value)
                            except (ValueError,TypeError):pass
            rev=d.get('revision'); down=d.get('down_revision')
            if not rev or rev in seen:errors.append('duplicate or missing revision: '+f.name)
            if rev:seen.add(rev)
            parents=([down] if isinstance(down,str) else list(down or []))
            rows.append((f.name,rev,parents));referenced.update(parents)
        except (SyntaxError,UnicodeError) as exc: errors.append(str(exc))
    for name,rev,parents in rows:
        for p in parents:
            if p not in seen:errors.append(f'{name}: missing parent {p}')
    heads=seen-referenced
    if len(heads)!=1:errors.append('expected exactly one head, got: '+str(heads))
    print('Migration revisions:',len(rows),'heads:',sorted(heads),'errors:',errors,flush=True)
    return not errors

if __name__=='__main__':
    results={'migration_graph':migrations()}
    results['progress_unit_tests']=run('Progress unit tests',[sys.executable,'-m','pytest','-q', 'tests/test_progress_scope.py','tests/test_progress_rollup.py','tests/test_progress_stage_scheme.py','tests/test_progress_source_evidence.py','tests/test_progress_milestone_preview.py','tests/test_progress_milestone_policies.py','tests/test_progress_procurement_acceptance.py','tests/test_progress_permissions_phase17.py','tests/test_progress_monitor_scheduler.py','tests/test_progress_alert_rules.py'],BACKEND)
    results['backend_import']=run('Backend app import',[sys.executable,'-c','from app.main import app; print(len(app.routes))'],BACKEND,timeout=30)
    results['frontend_build']=run('Frontend production build',['npm','run','build'],FRONTEND,timeout=120)
    print('\nRELEASE GATE:', 'PASS' if all(results.values()) else 'BLOCKED',json.dumps(results,indent=2),flush=True)
    sys.exit(0 if all(results.values()) else 1)
