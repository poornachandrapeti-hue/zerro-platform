from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials.movement_journal_proposals import JournalLine, validate_lines, NewProposal

def line(d=0,c=0):return JournalLine(cost_code_id=1,debit=Decimal(str(d)),credit=Decimal(str(c)))

def test_balanced_proposal():
    assert validate_lines([line(d='100.10'),line(c='100.10')])=='100.10'

@pytest.mark.parametrize('lines',[[line(d=100),line(c=90)],[line(d=0,c=0),line(c=3)],[line(d=10,c=10),line(c=10)]])
def test_invalid_lines(lines):
    with pytest.raises(HTTPException):validate_lines(lines)

def test_invalid_currency():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        NewProposal(source_movement_line_id=1,currency='INR$',description='Test posting',lines=[line(d=5),line(c=5)])
