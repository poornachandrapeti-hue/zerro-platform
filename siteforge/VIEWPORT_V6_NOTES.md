# V6 Home layout adjustments

Based on provided 1665px-wide screenshot: anchor internal and partner profile to far right of top bar; retain daylight hero image and text contrast; increase internal KPI/module card sizes to better utilize 900px-tall viewport; align partner main columns and eliminate hardcoded 122px quick-action top margin; preserve independently scrollable sidebars at shorter heights.

Files changed:
- frontend/src/main.tsx (imports final V6 style last)
- frontend/src/viewport-v6.css (new scoped responsive overrides)

No RBAC/API/backend logic changed. This is a visual-source patch. The frontend build could not run offline: npm ci reports ENOTCACHED for yallist 3.1.1. Deployment/browser behavior remains unverified.
