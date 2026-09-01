# Nexo mobile design QA

## Evidence

- Source visual truth: `/tmp/codex-remote-attachments/01a05d3b-8e50-7f90-bb0a-4df5de364216/049F207E-12E4-4682-966C-2CACEA614D1C/1-Photo-1.jpg` (589 × 1280 px, browser chrome included).
- Normalized source: `/tmp/roxy-design-qa/source-mobile.jpg` (390 × 847 px).
- Browser-rendered implementation: `/tmp/roxy-design-qa/implementation-mobile-final.png` (390 × 844 px, CSS viewport 390 × 844, device pixel ratio 1).
- Side-by-side comparison: `/tmp/roxy-design-qa/nexo-weather-side-by-side-final.png` (1280 × 919 px).
- State: Nexo immersive radar active on a mobile viewport, RainViewer frame loaded, OpenStreetMap keyless fallback loaded, signed-out local weather copy visible.

## Full-view comparison

The implementation preserves the approved dark meteorological composition, cream/gold typography, round globe, radar intensity legend, timeline, location control, and live precipitation status. The requested product change is intentional: it removes the separate full-screen dialog and keeps the Nexo navigation visible so the globe is part of the same map experience. It also removes the visible `API KEY REQUIRED` watermark from the source state.

## Focused-region comparison

The heading, globe/radar layer, timeline card, close control, and bottom navigation were readable at 390 px. A separate crop was not needed because all critical controls and typography remain legible in the normalized full-view evidence.

## Required fidelity surfaces

- Fonts and typography: Georgia display heading and compact sans-serif operational text preserve Roxy Home hierarchy; no clipped heading or control label at 390 px.
- Spacing and layout rhythm: safe margins, round close control, globe prominence, and bottom timeline card match the reference density. Persistent Nexo navigation remains reachable by design.
- Colors and tokens: dark blue-black background, cream copy, gold accents, green live status, and vivid RainViewer colors remain consistent.
- Image quality and asset fidelity: MapLibre renders a round vector/raster globe with live RainViewer tiles; no placeholder art, fake cloud image, or key-required watermark is present.
- Copy and content: radar is explicitly identified as measured RainViewer precipitation. Ambient rain, snow, cloud, and fog effects are explicitly identified as Open-Meteo-driven visualization.

## Interaction and runtime checks

- Verified pause changes to reproduce, close returns to the nearby map, timeline and location controls remain reachable, and the panel reports `aria-hidden=true` after closing.
- Automatic transition is covered by the Google Maps `zoom_changed` threshold test and the bidirectional MapLibre zoom return logic.
- Browser console: no warnings or errors in the final mobile render.
- Automated tests: 33 Home/Nexo tests passed; `node --check assets/roxy_list.js` passed.

## Comparison history

- First pass P2: the keyless OpenStreetMap globe was too light compared with the reference, reducing radar contrast.
- Fix: increased raster desaturation/contrast and lowered maximum raster brightness to `0.22`.
- Post-fix evidence: `/tmp/roxy-design-qa/implementation-mobile-final.png`; the globe is visibly darker, radar colors remain legible, and no actionable P0/P1/P2 issue remains.

## Residual test gap

The local QA session had no authenticated household or valid Google Maps browser key, so the automatic visual crossfade was verified by implementation/tests while the final globe, controls, responsive layout, network tiles, and runtime console were verified in-browser.

final result: passed
