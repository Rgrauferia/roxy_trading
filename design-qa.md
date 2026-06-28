# Design QA: Roxy Crypto 2H Folder

Source visual: user-provided Crypto 2H folder reference image.
Prototype state: `http://localhost:8502/?view=Dashboard&module=crypto-2h&symbol=BTC/USD&market=crypto&tf=2h`

Checks completed:
- Crypto 2H folder shell renders with sidebar, topbar, Roxy hero, 2-hour update countdown, notification strip, opportunity table, featured 2H opportunity, Deriv-style 2-hour platform panel, operative chart area, bottom info panels, and bottom navigation.
- Living universe background is preserved in the folder and chart sections.
- Opportunity rows render as clickable links, not escaped code.
- Visible priority order matches the requested crypto folder: BTC/USDT, ETH/USDT, SOL/USDT, XRP/USDT, BNB/USDT.
- Crypto icons render through Simple Icons URLs where available.
- Operative chart section renders two live chart iframes through the existing chart pipeline: 2H and 4H confirmation.
- Desktop DOM check: shell present, chart wrapper present, 5 clickable crypto rows, 11 crypto icon images, 2 visible chart iframes, 0 escaped crypto markup code blocks.
- Mobile DOM check at 393px width: shell width 385px, main width 367px, chart width 385px, document scroll width 393px, opportunity table scroll contained inside the panel, 2 visible chart iframes.
- Browser console error check returned no errors.

Known acceptable differences:
- Exact third-party icon availability depends on the Simple Icons CDN.
- Live chart content depends on current provider data availability.
- Screenshot capture is unreliable on this heavy Streamlit page with embedded chart iframes, so QA used DOM, layout, iframe, responsive, and console checks.

Final result: passed.
