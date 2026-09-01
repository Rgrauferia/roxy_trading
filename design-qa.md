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

---

# Deep pet personalization design QA

## Evidence

- Mobile browser render: `/private/tmp/roxy-nexo-fix.1La6Ve/.playwright-cli/page-2026-09-01T19-15-08-990Z.png` (390 × 844 px).
- Tested profile: Luna, adult Golden Retriever, large size, ideal body condition, moderate activity, current food and a maintain-weight goal.

## Interaction and runtime checks

- Verified the five-step profile flow uses dog-specific allergy, condition and goal choices and exposes a searchable exact-breed list.
- Verified the saved profile opens a dedicated hub with 10 dog recipes, concrete branded products with official-source links, and a private medical-history tab.
- Verified adding a product writes the exact brand and product to the existing shopping list without inventing price or completing a purchase.
- Verified a dated veterinary record persists and renders in the pet's medical timeline.
- Mobile layout at 390 px preserves readable hierarchy, 44 px-class controls, a reachable tab bar and the existing cream/forest/gold Roxy Home identity.
- Product filtering was tightened after QA so goal- or condition-specific products are omitted unless the pet profile actually matches them.
- “Ninguna alergia conocida” is no longer counted or presented as a dietary restriction.

## Validation

- `node --check assets/roxy_list.js` passed.
- 43 Home list/family/food tests passed before the final precision adjustment; the full suite is rerun before deployment.

final result: passed

---

# Personalized pet care and recipe onboarding design QA

## Evidence

- Source visual truth (selected option 1): `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-6114c5b3-1a8f-4f49-8fb2-bac4ebe0f997.png`.
- Production hero asset: `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-c25a30d7-5fe7-4e45-afcd-d0e0f0c8ac00.png`.
- Browser-rendered onboarding: `/Users/robertograu/.codex/visualizations/2026/09/01/01a05d3b-8e50-7f90-bb0a-4df5de364216/pet-onboarding-implemented-390.png` (390 px application surface captured in the in-app browser).
- Browser-rendered questionnaire: `/Users/robertograu/.codex/visualizations/2026/09/01/01a05d3b-8e50-7f90-bb0a-4df5de364216/pet-profile-step1-implemented-390.png`.
- Same-input comparison: `/Users/robertograu/.codex/visualizations/2026/09/01/01a05d3b-8e50-7f90-bb0a-4df5de364216/pet-onboarding-comparison.png`.

## Full-view comparison

The implementation keeps the selected direction's cream, forest and gold identity, large editorial headline, multi-species household image, five-part care journey, veterinary safety promise, and one clear add-pet action. It intentionally uses the existing Roxy Home header and bottom navigation rather than replacing product chrome with mock-only navigation.

## Focused-region comparison

The empty state no longer competes with recipe-import cards or a generic pet catalog. The five profile stages remain readable at 390 px, the generated animal image has an intentional crop, and the questionnaire opens as a compact mobile sheet with full-width fields and controls.

## Required fidelity surfaces

- Typography and hierarchy: Georgia display headings and existing sans-serif operational copy match Roxy Home.
- Spacing and layout: the onboarding card, hero, steps, safety message, and CTA follow one continuous vertical rhythm with mobile-safe targets.
- Colors and assets: production uses the approved cream/forest/gold palette and a real generated bitmap asset; no emoji, CSS animal art, placeholder boxes, or handcrafted SVGs are used.
- Product behavior: pet mode with no profile shows only onboarding. The five steps cover identity, health, food, environment, and routines; environment prompts adapt for aquarium, terrarium, amphibian habitat, bird space, or household context.
- Safety and personalization: allergies filter matching recipes, veterinarian instructions remain explicit, and homemade recipes are not represented as complete medical diets.

## Interaction and runtime checks

- Verified audience switching, no-profile gating, opening and closing the questionnaire, required-field validation, step navigation, fish-specific aquarium copy, and persisted species-specific profile fields.
- Browser console: no warnings or errors during the onboarding and questionnaire journey.
- Automated tests: 42 Home/list/family/food tests passed; `node --check assets/roxy_list.js` passed.

## Comparison history

- First pass P2: recipe-import content remained above the onboarding, weakening the selected option's single primary action.
- Fix: pet no-profile mode now reduces that area to the audience selector and hides the recipe import and generic catalog until a pet exists.
- First pass P2: collapsing the import area could preserve a stale scroll offset after selecting pet mode.
- Fix: the audience control receives a scroll margin and the no-profile transition recenters it before presenting onboarding.
- Post-fix result: no actionable P0/P1/P2 visual or interaction issue remains.

final result: passed

---

# Nexo person and place marker design QA

## Evidence

- Source visual truth (selected option 1): `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-24a6163f-b9fe-4326-b197-1b8a206ab6ed.png` (853 × 1844 px). The selected people-only option is `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-352410f6-9472-4b8a-b2ec-b9022bc44313.png` (853 × 1844 px).
- Browser-rendered implementation: `/Users/robertograu/.codex/visualizations/2026/09/01/01a05d3b-8e50-7f90-bb0a-4df5de364216/nexo-markers-implementation.png` (1280 × 720 px, CSS viewport 1280 × 720, device pixel ratio 1).
- Side-by-side comparison: `/Users/robertograu/.codex/visualizations/2026/09/01/01a05d3b-8e50-7f90-bb0a-4df5de364216/nexo-markers-comparison.png`.
- State: two live people markers, Home selected, Work collapsed, Store selected during the interaction check.

## Full-view comparison

The implementation preserves the selected option's hierarchy: people remain the strongest elements through real profile photos, a clean cream/white halo, a small green live-state icon, and a detached cream label. Saved locations use smaller architectural badges with type-specific Material Symbols and only the selected place exposes its name.

## Focused-region comparison

The person portraits, live indicator, label cards, Home badge, Work badge, Store badge, and expanded/collapsed label states are all readable in the browser render and side-by-side evidence. No additional crop was needed because the implementation evidence renders these components at full browser density and the comparison clearly distinguishes their hierarchy.

## Required fidelity surfaces

- Fonts and typography: compact sans-serif labels match the existing Nexo map UI; names are stronger than status text and place names remain short and scannable.
- Spacing and layout rhythm: portrait and label are separated by 7 px; place badges are 42 px with a minimum 44 px target; markers do not overlap their own labels.
- Colors and visual tokens: cream/white surfaces, forest text, gold active state, green live state, slate Work, and terracotta Store preserve Roxy Home's palette.
- Image quality and asset fidelity: production continues to use each member's real stored profile photo. The QA harness used existing Roxy image assets; no placeholder shape replaces avatars in production.
- Copy and content: live people use `Ubicación compartida` when no richer status exists. Place labels use the saved user name and are not permanently expanded.
- Icons: all live and place symbols come from the existing Material Symbols Rounded library; there are no handcrafted SVG or emoji substitutes.
- Accessibility and interaction: overlays are semantic buttons, expose descriptive labels, keep 44 px minimum place targets, and update `aria-expanded` when a place is selected.

## Browser checks

- Verified two people markers and three saved-place marker types render.
- Verified selecting Store expands Store and collapses Home.
- Browser console: no warnings or errors.
- Automated tests: 33 Home/Nexo tests passed; `node --check assets/roxy_list.js` passed.

## Comparison history

- First pass P2: saved-place targets rendered at 38 px, below the practical 44 px mobile target.
- Fix: increased architectural badges to 42 px and the semantic button target to a minimum of 44 × 44 px.
- Post-fix evidence: source CSS and browser-rendered component hierarchy; no actionable P0/P1/P2 issue remains.

## Residual test gap

The local browser has no authenticated household Google Maps key, so marker visuals and interactions were verified in a MapLibre QA harness using the exact production classes. Google OverlayView placement and saved-place data wiring are covered by implementation and automated tests; final public asset/version verification is still required after deployment.

final result: passed
