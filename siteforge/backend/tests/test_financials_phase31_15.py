from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials.router import financial_period_start, enforce_open_financial_period


def test_period_utc_month():
    assert financial_period_start(datetime(2026,12,31,23,20,tzinfo=timezone.utc)).isoformat()=="2026-12-01T00:00:00+00:00"


def test_naive_timestamp_rejected():
    with pytest.raises(HTTPException) as exc:
        financial_period_start(datetime(2026,12,1))
    assert exc.value.status_code==422


def test_closed_period_blocks_new_posting():
    db=MagicMock()
    db.query.return_value.filter_by.return_value.with_for_update.return_value.one_or_none.return_value=SimpleNamespace(status='Closed')
    with pytest.raises(HTTPException) as exc:
        enforce_open_financial_period(db,1,'INR',datetime(2026,10,15,tzinfo=timezone.utc))
    assert exc.value.status_code==409


def test_open_period_permits_posting():
    db=MagicMock()
    db.query.return_value.filter_by.return_value.with_for_update.return_value.one_or_none.return_value=SimpleNamespace(status='Open')
    enforce_open_financial_period(db,1,'INR',datetime(2026,10,15,tzinfo=timezone.utc))
