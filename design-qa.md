# Design QA: Roxy Crypto Daily Folder

Source visual: user-provided Crypto Daily folder reference image.
Prototype state: `http://localhost:8502/?view=Dashboard&module=crypto-daily&symbol=BTC/USD&market=crypto&tf=1d`

Checks completed:
- Crypto Daily folder shell renders with sidebar, topbar, Roxy hero, 24-hour update countdown, notification strip, opportunity table, featured Daily opportunity, Deriv-style Daily platform panel, operative chart area, macro panels, key levels, events, alerts, tips, and bottom navigation.
- Living universe background is preserved in the folder and chart sections.
- Opportunity rows render as clickable links, not escaped code.
- Visible priority order matches the requested crypto folder: BTC/USDT, ETH/USDT, SOL/USDT, XRP/USDT, BNB/USDT.
- Crypto icons render through Simple Icons URLs where available.
- Operative chart section renders two live chart iframes through the existing chart pipeline: 1D and 1W confirmation.
- Selecting a crypto row updates the folder URL, selected row, and chart header. SOL/USDT was verified after navigation with 2 visible chart iframes.
- Desktop DOM check: shell present, chart wrapper present, 5 clickable crypto rows, 11 crypto icon images, 2 visible chart iframes at 543px x 330px, 0 escaped crypto markup code blocks.
- Mobile DOM check at 393px width: shell width 385px, chart width 385px, document scroll width 393px, insights and bottom panels collapse to one column, 2 visible chart iframes at 361px x 330px.
- Browser console error check returned no errors.

Known acceptable differences:
- Exact third-party icon availability depends on the Simple Icons CDN.
- Live chart content depends on current provider data availability.
- Screenshot capture is unreliable on this heavy Streamlit page with embedded chart iframes, so QA used DOM, layout, iframe, responsive, and console checks.

Final result: passed.
