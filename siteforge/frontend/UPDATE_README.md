# ZerroBuild homepage update

Replace your existing frontend folder with this frontend folder after backing up local changes. No backend change or new dependency is required.

Run from frontend:

```sh
npm ci
npm run dev
```

The existing Vite configuration proxies /api to localhost:8000. Keep your backend running there, or retain your own deployment proxy configuration. For production run `npm run build`.

## Changes

- Full-width 208px construction hero; sidebar navigation starts below it.
- One shared photographic background across the hero and sidebar, preventing a patched corner.
- Brand appears once on Home, with white Zerro and orange Build.
- 232px sidebar, six lifecycle cards, all 22 tiles, support ribbon, and visible SVG module icons.
- Three desktop columns; vertical scrolling at shorter heights. Smaller screens adapt to fewer columns.
- Existing API calls, module availability checks, permissions, destinations and notification counts retained. No sample notification count or simulated API is embedded in the app.

Primary files: src/home/design.css, src/home/poster/designIcons.tsx, src/home/poster/ConstructionHero.tsx, src/home/poster/lifecycleConfig.ts, src/App.tsx, src/home.tsx, src/main.tsx, public/construction-scene.png.

## Validation

Production TypeScript/Vite build passed. Existing application bundle-size warning remains.
Headless browser checks at 1536x1024, 1440x900 and 1366x768 found 22 module tiles and no horizontal overflow. Verified exact tile background colors and full-width hero/232px sidebar dimensions. Browser screenshots inspected; preview included in docs. Project Details navigation verified without browser runtime errors using simulated auth/catalog/project responses.

Your backend was not supplied; live authentication and backend workflows were not tested. Unimplemented modules remain disabled with their existing explanatory tooltips. The photographic asset is a clean recreation of the approved concept, and SVG icons/type are implemented equivalents, not a pixel-identical raster copy. Desktop content scrolls below the fold at shorter resolutions.
