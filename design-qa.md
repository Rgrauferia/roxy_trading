# Roxy dashboard design QA

- Source visual truth: `/tmp/codex-remote-attachments/019f76dc-7cec-7ca2-a72e-9dcc2b978a54/090ABABB-F970-4ACC-9C74-B3F50125D32E/3-Photo-3.jpg`
- Intended viewport: 390 × 844 mobile
- Intended state: authenticated Dashboard, AAPL selected, no folder open
- Implementation screenshot: unavailable; the in-app browser webview timed out for both the local and Render URLs, and no Chrome browser connection was available.

## Full-view comparison evidence

Blocked. The source screenshot is available, but a browser-rendered implementation screenshot could not be captured in the current session. Code inspection, HTTP health, startup smoke tests, and unit/integration tests are not substitutes for the required visual comparison.

## Focused region comparison evidence

Blocked for the same reason. The regions that still require direct comparison are the Roxy portrait crop, five-folder row, live chart area, top bar, and bottom navigation.

## Findings

- [P0] Browser-rendered evidence is unavailable.
  - Location: mobile Dashboard on the public Render deployment.
  - Evidence: both browser attempts timed out before the webview attached; the fallback Chrome connection was unavailable.
  - Impact: typography, spacing, colors, image crop, copy density, and responsive fidelity cannot be truthfully approved from code alone.
  - Fix: capture the deployed Dashboard at 390 × 844 and compare it directly with the source screenshot before declaring visual QA complete.

## Interaction checks completed outside visual QA

- The five folders submit explicit GET navigation state: `view`, `symbol`, `market`, `tf`, and `module`.
- Folder controls use full-card tap targets and `touch-action: manipulation` for mobile Safari.
- The duplicated Safari portrait layer was removed; the hologram now embeds one JPEG while retaining the face rig.
- The complete automated suite passed: 2702 tests.
- GitHub CI and the Streamlit startup smoke test passed for commit `e7f9d04a7`.

## Comparison history

- Initial pass: blocked before visual comparison because no implementation screenshot could be captured.
- No visual fixes were inferred after the block; the remaining approval requires new browser-rendered evidence.

## Implementation checklist

- Capture the authenticated public Dashboard at 390 × 844.
- Test each of the five folder controls and confirm the URL/module workspace changes.
- Compare the full screen and focused portrait/folder/chart regions with the source.
- Resolve any P0/P1/P2 differences, repeat capture, and change the final result only after the comparison passes.

final result: blocked

---

# Roxy Home shared-family hero QA

- Source visual truth: `artifacts/roxy-home-family-hero/reference.jpg`
- Intended viewport: 390 × 844 mobile
- Intended state: authenticated Roxy Home shopping view at the top of the page
- Implementation screenshot: `artifacts/roxy-home-family-hero/implementation-mobile.png`
- Public URL: `https://roxy-home.onrender.com/lista`

## Full-view comparison evidence

The published mobile view preserves the reference's warm cream home atmosphere, oversized dark-green serif greeting, gold date/detail line, arched window, and leafy plant. The personalized name was intentionally replaced with the shared label `familia`. The existing Roxy Home header, command input, quick actions, shopping list, and bottom navigation remain in their established positions.

## Focused region comparison evidence

- The date displays the device-local weekday, day, month, and year in Spanish.
- The time displays the device-local hour and minute.
- The greeting changes between `Buenos días`, `Buenas tardes`, and `Buenas noches`.
- The decorative plant image is loaded at its optimized 1200 × 800 size and is ignored by assistive technology.
- The Roxy command bar remains fully visible and usable inside the hero.

## Findings

- Initial comparison: the hero asset returned 404 because the Home Docker image copied only the product-image subdirectory.
- Fix: added the dedicated hero asset to `Dockerfile.roxy-home`, redeployed, and verified the public asset returns HTTP 200.
- Final comparison: no blocking visual differences. At 390 × 844 the document width is exactly 390 px, there is no horizontal overflow, the background image is loaded, and browser logs contain no errors or warnings.

## Interaction and regression checks

- 32 Home-focused tests passed across shopping, habitual-product memory, Home AI, recipes, cooking, and API flows.
- Dynamic date/time semantics use a real `<time>` element with an ISO datetime value.
- PWA cache advanced to v18 and includes the family hero for offline reopening.
- Docker build could not run locally because the Docker daemon was not available; the real Render Docker deployment succeeded and served the image.

final result: passed
