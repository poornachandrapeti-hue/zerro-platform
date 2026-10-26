"""QA revocation review tasks must not be mutated via generic task changes."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'app' / 'domains'


def test_generic_task_update_rejects_all_impact_task_changes_before_mutation():
    source = (ROOT / 'coordination' / 'service.py').read_text()
    tree = ast.parse(source)
    func = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'change_task')
    branch = next(node for node in func.body if isinstance(node, ast.If)
                  and 'stores.qa_revocation.construction_review' in ast.get_source_segment(source, node.test))
    assert len(branch.body) == 1 and isinstance(branch.body[0], ast.Raise)
    guard = ast.get_source_segment(source, branch)
    assert 'status in' not in guard and 'owner_id' not in guard
    first_update = source.index('task.owner_id = owner_id', source.index('def change_task('))
    assert branch.lineno < source[:first_update].count('\n') + 1


def test_domain_review_only_uses_named_ack_and_qa_verify_endpoints():
    source = (ROOT / 'stores_inventory' / 'qa_issued_impact.py').read_text()
    assert "task.status = 'In Progress'" in source
    assert "task.status = 'Completed'" in source
    assert "task.evidence = 'Construction acknowledgment: '" in source
    assert "task.evidence += '\\nQA verification by user '" in source
