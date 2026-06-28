# Design QA: Roxy Actions Folder

Source visual: user-provided actions-folder reference image.
Prototype state: `http://localhost:8502/?view=Dashboard&module=acciones-operar&symbol=AAPL&market=stock&tf=1h`

Checks completed:
- Actions folder shell renders with sidebar, topbar, Roxy hero, intelligent filters, opportunity summary, signal panel, opportunity table, operative chart area, reason panel, news panel, and bottom navigation.
- Opportunity rows render as clickable links, not escaped code.
- Stock icons render through Simple Icons URLs where available.
- Operative chart section still renders live chart iframes through the existing chart pipeline.
- Mobile viewport keeps the shell within iPhone width and contains the opportunity table scroll inside its panel.

Known acceptable differences:
- Exact third-party icon availability depends on the Simple Icons CDN.
- Live chart content depends on current provider data availability.

Final result: passed.
