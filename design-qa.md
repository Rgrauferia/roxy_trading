# Design QA: Roxy Crypto 20min Folder

Source visual: user-provided Crypto 20min folder reference image.
Prototype state: `http://localhost:8502/?view=Dashboard&module=crypto-20m&symbol=BTC/USD&market=crypto&tf=1m`

Checks completed:
- Crypto 20min folder shell renders with sidebar, topbar, Roxy hero, update countdown, notification strip, opportunity table, featured opportunity, Deriv-style platform panel, operative chart area, bottom info panels, and bottom navigation.
- Living universe background is preserved in the folder and chart sections.
- Opportunity rows render as clickable links, not escaped code.
- Visible priority order matches the requested crypto folder: BTC/USDT, ETH/USDT, SOL/USDT, XRP/USDT, BNB/USDT.
- Crypto icons render through Simple Icons URLs where available.
- Operative chart section still renders live chart iframes through the existing chart pipeline.
- Desktop DOM check: shell present, chart wrapper present, 6 clickable crypto rows, 15 crypto icon images, 3 chart iframes, 0 escaped crypto markup code blocks.
- Mobile DOM check at 393px width: shell width 385px, main width 367px, chart width 385px, document scroll width 393px, opportunity table scroll contained inside the panel.

Known acceptable differences:
- Exact third-party icon availability depends on the Simple Icons CDN.
- Live chart content depends on current provider data availability.
- Browser screenshot capture timed out on this heavy Streamlit page with embedded chart iframes, so QA used DOM, layout, iframe, and responsive checks.

Final result: passed.
