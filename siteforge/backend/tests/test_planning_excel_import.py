import base64
import io
from openpyxl import Workbook
import pytest
from fastapi import HTTPException
from app.domains.planning_reporting.excel_import_router import unpack, COLUMNS


def book(rows):
    wb=Workbook();sheet=wb.active;sheet.title='Activities';sheet.append(COLUMNS)
    for row in rows:sheet.append(row)
    buffer=io.BytesIO();wb.save(buffer)
    return base64.b64encode(buffer.getvalue()).decode()


def test_excel_template_parser():
    data, rows=unpack(book([['CV-1','Pile test','CIV','Task',16,1,'STD','','']]))
    assert data[:2]==b'PK'
    assert rows[0][0]==2
    assert rows[0][1]['activity_code']=='CV-1'
    assert rows[0][1]['duration_hours']==16


def test_empty_rows_skipped():
    _,rows=unpack(book([['CV-2','Survey','CIV','Milestone',0,1,'STD','',''],[None]*len(COLUMNS)]))
    assert len(rows)==1


def test_invalid_bytes_rejected():
    with pytest.raises(HTTPException) as caught:unpack(base64.b64encode(b'not excel').decode())
    assert caught.value.status_code==422


def test_missing_headings_rejected():
    wb=Workbook();sheet=wb.active;sheet.title='Activities';sheet.append(['activity_code'])
    buffer=io.BytesIO();wb.save(buffer)
    with pytest.raises(HTTPException) as caught:unpack(base64.b64encode(buffer.getvalue()).decode())
    assert caught.value.status_code==422
