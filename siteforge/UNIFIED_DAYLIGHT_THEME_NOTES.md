# Unified Daylight Theme Update

This package updates ZerroBuild to use a consistent light industrial banner treatment across the UI.

## Applied changes
- Home dashboard welcome banner uses the approved light contrast style.
- Partner dashboard banner uses the same image, brightness, and text contrast.
- Module intro sections across the authenticated UI now use the same banner language.
- Overall app canvas is lightened to avoid the previous overly dark appearance.
- Sidebar remains dark navy for structure and navigation clarity.
- Working surfaces (cards, tables, forms) remain white and readable.

## Files changed
- `frontend/src/style.css`
- `frontend/src/home/design.css`

## Notes
- This update is visual only.
- Backend, RBAC, drawing import behavior, and database logic are unchanged.
