# Welcome clipping fix V13

The V12 negative positioning was being clipped by V9's main-column overflow rules, hiding the beginning of the heading and subtitle.

- Added final home-scoped stylesheet `frontend/src/welcome-fix-v13.css` after V12.
- Allowed the hero's shifted content to render beyond the main grid-column boundary.
- Kept the partner Vendor / Supplier / Contractor controls in their own row below the hero.
- Preserved existing content, APIs, project names, routes, authentication and RBAC.

This fixes clipping in the source but a browser test at the user's actual screen size is still required.
