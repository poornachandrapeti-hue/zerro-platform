from unittest.mock import Mock
from sqlalchemy.sql.elements import TextClause
from app.domains.stores_inventory.idempotency_lock import lock_request_key


def test_scoped_advisory_lock_uses_bound_parameter():
    db = Mock()
    lock_request_key(db, organization_id=2, project_id=17, key="abc';drop table x;--", namespace='lot-reservation')
    statement, params = db.execute.call_args.args
    assert isinstance(statement, TextClause)
    assert ':lock_name' in str(statement)
    assert params['lock_name'] == "stores:lot-reservation:2:17:abc';drop table x;--"


def test_empty_key_fails_closed():
    import pytest
    with pytest.raises(ValueError):
        lock_request_key(Mock(), organization_id=2, project_id=17, key='  ', namespace='lot-reservation')


def test_writer_locks_before_existing_key_lookup():
    import inspect
    from app.domains.stores_inventory.lot_reservations import reserve_lot
    source = inspect.getsource(reserve_lot)
    assert source.index('lock_request_key(db,') < source.index('existing = db.execute(')
