"""Material lines from explicit tables on a drawing file.

Only rows of a table whose header names a description and a quantity column are read.
Nothing is calculated from geometry, scale or pixels. A missing quantity or unit stays
missing and is flagged for the reviewer.
"""

import re
from decimal import Decimal, InvalidOperation
from io import BytesIO

from app.config import settings

DESCRIPTION = {
    "description", "item description", "material description", "material", "item", "component",
    "particulars", "description of material", "material name", "name",
}
SPECIFICATION = {
    "specification", "spec", "size", "material spec", "grade", "rating", "standard", "size rating",
    "material grade", "dimensions", "type", "spec size",
}
QUANTITY = {"qty", "quantity", "quan", "qnty", "total qty", "total quantity", "qty nos", "req qty", "no of"}
UNIT = {"unit", "uom", "units", "unit of measure", "u m"}
REFERENCE = {"mark", "tag", "item no", "pos", "position", "sr no", "s no", "sl no", "ref", "reference", "part no"}
KNOWN_UNITS = {
    "m", "mm", "cm", "km", "rm", "lm", "m2", "sqm", "m3", "cum", "kg", "t", "mt", "ton", "tons", "g",
    "l", "ltr", "litre", "nos", "no", "nr", "ea", "each", "pcs", "pc", "set", "sets", "lot", "pair",
    "roll", "rolls", "bag", "bags", "box", "length", "lengths", "coil", "drum", "sheet", "sheets",
}
SUPPORTED = ("PDF with a text layer: native table extraction",)
NUMBER = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*([A-Za-z][A-Za-z0-9²³/.]*)?\s*$")


class ExtractionProblem(Exception):
    """A clear, user-facing reason extraction could not run."""

    def __init__(self, message, status="Failed"):
        super().__init__(message)
        self.status = status


def _norm(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def unit_key(value):
    return _norm(value).replace(" ", "").replace("²", "2").replace("³", "3")


def parse_pages(text, count):
    text = (text or "").strip()
    if not text:
        return list(range(1, count + 1))
    pages = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+))?", part)
        if not match:
            raise ExtractionProblem(f"Pages '{text}' are not valid. Use numbers like 1,3-4")
        first = int(match.group(1))
        last = int(match.group(2) or first)
        if first < 1 or last < first:
            raise ExtractionProblem(f"Pages '{text}' are not valid. Use numbers like 1,3-4")
        if last > count:
            raise ExtractionProblem(f"Page {last} is not in this file. It has {count} page(s)")
        pages.extend(range(first, last + 1))
    return list(dict.fromkeys(pages))


def validate_pages(text):
    if (text or "").strip():
        parse_pages(text, 10_000)
    return (text or "").strip()


def _columns(header):
    names = [_norm(cell) for cell in header]
    found = {}
    described = [index for index, name in enumerate(names) if "description" in name]
    if described:
        found["description"] = described[0]
    for index, name in enumerate(names):
        if index in found.values():
            continue
        for key, options in (
            ("description", DESCRIPTION),
            ("specification", SPECIFICATION),
            ("quantity", QUANTITY),
            ("unit", UNIT),
            ("reference", REFERENCE),
        ):
            if key not in found and (name in options or (key == "quantity" and name.startswith("qty"))):
                found[key] = index
                break
    if "description" in found and "quantity" in found:
        return found
    return None


def _quantity(raw):
    text = str(raw or "").strip()
    if not text:
        return None, "", ["Missing quantity"]
    match = NUMBER.match(text)
    if not match:
        return None, "", [f"Quantity '{text}' is not a number"]
    try:
        value = Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        return None, "", [f"Quantity '{text}' is not a number"]
    if value <= 0:
        return None, "", [f"Quantity '{text}' is not above zero"]
    return value, (match.group(2) or ""), []


def lines_from_table(rows, page, table_ref, row_boxes=None, base_confidence=Decimal("0.95"), cell_confidence=None):
    """Rows of one table to material lines. Returns [] when the table is not a material table."""
    header_at = None
    columns = None
    for index, row in enumerate(rows[:3]):
        columns = _columns(row)
        if columns:
            header_at = index
            break
    if columns is None:
        return []
    result = []
    for index, row in enumerate(rows[header_at + 1 :], start=header_at + 2):
        cells = [str(cell or "").replace("\n", " ").strip() for cell in row]

        def cell(name):
            at = columns.get(name)
            return cells[at] if at is not None and at < len(cells) else ""

        description = cell("description")
        if not any(cells):
            continue
        if not description:
            continue
        quantity, unit_in_quantity, flags = _quantity(cell("quantity"))
        unit = cell("unit")
        if not unit and unit_in_quantity:
            unit = unit_in_quantity
            flags.append("Unit read from the quantity cell")
        if not unit:
            flags.append("Missing unit")
        elif unit_key(unit) not in KNOWN_UNITS:
            flags.append(f"Unit '{unit}' is not a recognised unit")
        confidence = base_confidence
        if cell_confidence is not None and index - 1 < len(cell_confidence):
            confidence = Decimal(str(cell_confidence[index - 1]))
        if quantity is None:
            confidence -= Decimal("0.3")
        if not unit:
            confidence -= Decimal("0.2")
        elif "Unit read from the quantity cell" in flags:
            confidence -= Decimal("0.1")
        confidence = max(Decimal("0.05"), min(Decimal("1"), confidence)).quantize(Decimal("0.001"))
        box = None
        if row_boxes and index - 1 < len(row_boxes) and row_boxes[index - 1]:
            box = [round(float(value), 1) for value in row_boxes[index - 1]]
        result.append(
            {
                "description": description[:2000],
                "specification": cell("specification")[:2000],
                "quantity": quantity,
                "unit": unit[:20],
                "reference": cell("reference")[:80],
                "page": page,
                "table_ref": table_ref,
                "row_ref": str(index),
                "bbox": box,
                "confidence": confidence,
                "flags": flags,
                "original": {"cells": cells, "header": [str(c or "") for c in rows[header_at]]},
            }
        )
    return result


def _native(data, pages_text):
    try:
        import pdfplumber
    except ImportError as exc:
        raise ExtractionProblem("The PDF reader is not installed on the server", "Needs setup") from exc
    lines, scanned, tables_seen = [], [], 0
    try:
        pdf = pdfplumber.open(BytesIO(data))
    except Exception as exc:
        raise ExtractionProblem("The PDF could not be opened. It may be damaged or password protected") from exc
    with pdf:
        pages = parse_pages(pages_text, len(pdf.pages))
        for number in pages:
            page = pdf.pages[number - 1]
            if not page.chars:
                scanned.append(number)
                continue
            found = []
            for strategy in (None, {"vertical_strategy": "text", "horizontal_strategy": "text"}):
                tables = page.find_tables(strategy) if strategy else page.find_tables()
                for t_index, table in enumerate(tables, start=1):
                    tables_seen += 1
                    rows = table.extract()
                    boxes = [getattr(row, "bbox", None) for row in getattr(table, "rows", [])]
                    ref = f"T{t_index}" if strategy is None else f"T{t_index} (text layout)"
                    found.extend(lines_from_table(rows, number, ref, boxes))
                if found:
                    break
            lines.extend(found)
    return lines, scanned, pages, tables_seen


def ocr_configured():
    return bool(settings.ocr_provider and settings.ocr_endpoint)


def ocr_status():
    if ocr_configured():
        return {
            "configured": True,
            "provider": settings.ocr_provider,
            "message": f"Scanned pages are sent to the {settings.ocr_provider} OCR/table service configured on the server.",
        }
    return {
        "configured": False,
        "provider": "",
        "message": "No OCR/table provider is configured on the server. Scanned drawings and images cannot be extracted. Enter lines by hand or import an MTO file.",
    }


def _ocr(data, filename, content_type, pages):
    """Send the file to the configured OCR/table service.

    Expected JSON reply: {"tables": [{"page": 1, "rows": [["Description", "Qty", ...], ...],
    "row_boxes": [[x0, top, x1, bottom], ...], "row_confidence": [0.9, ...]}]}
    """
    import httpx

    headers = {"Authorization": f"Bearer {settings.ocr_api_key}"} if settings.ocr_api_key else {}
    try:
        response = httpx.post(
            settings.ocr_endpoint,
            headers=headers,
            data={"pages": ",".join(str(page) for page in pages)},
            files={"file": (filename, data, content_type or "application/octet-stream")},
            timeout=settings.ocr_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise ExtractionProblem(f"The OCR/table service could not be reached: {exc.__class__.__name__}") from exc
    if response.status_code >= 400:
        raise ExtractionProblem(f"The OCR/table service returned an error ({response.status_code})")
    try:
        tables = response.json().get("tables", [])
    except ValueError as exc:
        raise ExtractionProblem("The OCR/table service reply was not valid JSON") from exc
    lines = []
    for t_index, table in enumerate(tables, start=1):
        lines.extend(
            lines_from_table(
                table.get("rows") or [],
                int(table.get("page") or 1),
                f"OCR T{t_index}",
                table.get("row_boxes"),
                Decimal("0.8"),
                table.get("row_confidence"),
            )
        )
    return lines


def extract(data, filename, content_type, pages_text):
    """Returns (lines, provider, message). Raises ExtractionProblem with a clear reason."""
    name = (filename or "").lower()
    is_pdf = name.endswith(".pdf") or (content_type or "") == "application/pdf" or data[:5] == b"%PDF-"
    is_image = name.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff"))
    if not is_pdf and not is_image:
        raise ExtractionProblem(
            "This drawing file type is not supported for extraction. Supported: PDF with a text layer, "
            "and scanned PDF or images when an OCR/table provider is configured. "
            "Enter lines by hand or import an MTO file."
        )
    if is_image:
        if not ocr_configured():
            raise ExtractionProblem(ocr_status()["message"], "Needs setup")
        lines = _ocr(data, filename, content_type, [1])
        provider = f"ocr:{settings.ocr_provider}"
        if not lines:
            raise ExtractionProblem("No material table with description and quantity columns was found on this image. Enter lines by hand or import an MTO file.")
        return lines, provider, f"{len(lines)} line(s) read by the OCR/table service."
    lines, scanned, pages, tables_seen = _native(data, pages_text)
    provider = "native-pdf"
    notes = []
    if scanned:
        if ocr_configured():
            lines.extend(_ocr(data, filename, content_type, scanned))
            provider = f"native-pdf+ocr:{settings.ocr_provider}"
        elif not lines:
            raise ExtractionProblem(
                f"Page(s) {', '.join(map(str, scanned))} have no text layer (scanned). "
                + ocr_status()["message"],
                "Needs setup",
            )
        else:
            notes.append(
                f"Page(s) {', '.join(map(str, scanned))} are scanned and were skipped because no OCR/table provider is configured."
            )
    if not lines:
        raise ExtractionProblem(
            f"No material table with description and quantity columns was found on page(s) {', '.join(map(str, pages))} "
            f"({tables_seen} table area(s) checked). Enter lines by hand or import an MTO file."
        )
    flagged = sum(1 for line in lines if line["flags"])
    notes.insert(0, f"{len(lines)} line(s) read from the drawing. {flagged} need attention.")
    return lines, provider, " ".join(notes)
