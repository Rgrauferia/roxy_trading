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

## Mascotas simplificado · versión 136

**Source visual truth**

- `/tmp/codex-remote-attachments/01a05d3b-8e50-7f90-bb0a-4df5de364216/163538BC-E0A6-4B2C-B93C-A73F5FA898BC/1-Photo-1.jpg`
- La referencia se usa para identidad visual, jerarquía editorial, fotografía circular, crema/verde/dorado y navegación compacta. Los controles del editor y el navegador presentes en la imagen no pertenecen al producto.

**Implementation evidence**

- `artifacts/pet-information-fold-v135.png`
- `artifacts/pet-products-fold-v135.png`
- `artifacts/pet-reference-vs-information-fold-v135.png`
- Viewport CSS: 390 × 844, device scale factor 1.
- Source: 589 × 1280 px; normalizada a 390 × 844 para la comparación del área visible.
- Implementation: 390 × 844 px. Estado: Luna / Información y Luna / Productos.

**Full-view comparison**

- Se comparó la referencia y la ficha Información juntas en `pet-reference-vs-information-fold-v135.png`.
- La nueva pantalla conserva el retrato circular, tipografía editorial, paleta y navegación en cuatro áreas, pero elimina deliberadamente progreso, rutina y pasaporte porque el nuevo alcance pide únicamente información, historial, recetas y productos.

**Focused evidence**

- `pet-products-fold-v135.png` y la captura larga `pet-products-mobile-v135.png` verifican fotografías oficiales, marca, nombre, motivo de recomendación, fuente oficial y CTA de carrito para los tres productos de hurón.

**Fidelity surfaces**

- Typography: jerarquía Georgia + sans existente, peso y saltos legibles; sin truncamiento.
- Spacing: ritmo compacto, tarjetas alineadas, cuatro pestañas iguales y navegación persistente sin ocultar controles en viewport.
- Colors: crema, verde bosque y dorado del sistema actual; contraste suficiente en seleccionado y CTA.
- Images: fotografía de mascota cuando existe; las recomendaciones visibles de hurón usan imágenes oficiales de Mazuri, Oxbow y Wysong con `object-fit: contain`.
- Copy: términos claros y personalizados; riesgo veterinario y decisión de compra quedan explícitos.

**Interactions tested**

- Información, Historial, Recetas y Productos cambian de estado y `aria-selected` correctamente.
- Añadir al carrito creó el artículo de prueba y mostró confirmación.
- Historial presenta descargas separadas para expediente completo y vacunas, alta de registros y documentos.
- Consola: sin errores.
- Verificación pública: versión 136 cargada; Luna y su información persistieron después de recargar.

**Findings**

- No quedan diferencias P0, P1 o P2 dentro del alcance aprobado.
- P3: el perfil de QA sin foto usa el icono oficial del módulo; un perfil real conserva su fotografía guardada.

**Comparison history**

- Primera captura larga: la barra fija aparecía intercalada por el mecanismo de captura full-page, no por el layout del viewport.
- Corrección de evidencia: se recapturó a 390 × 844 y se comparó el mismo pliegue visual; la barra permanece correctamente anclada al borde inferior.

final result: passed

---

# Pet passport redesign QA · version 134

## Evidence

- Source visual truth: `/tmp/codex-remote-attachments/01a05d3b-8e50-7f90-bb0a-4df5de364216/163538BC-E0A6-4B2C-B93C-A73F5FA898BC/1-Photo-1.jpg` (589 × 1280 px).
- Secondary source: `/tmp/codex-remote-attachments/01a05d3b-8e50-7f90-bb0a-4df5de364216/163538BC-E0A6-4B2C-B93C-A73F5FA898BC/2-Photo-2.jpg` (589 × 1280 px).
- Browser-rendered implementation: `/private/tmp/roxy-nexo-fix.1La6Ve/artifacts/pet-passport-mobile-fold-v134.png` (390 × 844 px, CSS viewport 390 × 844, device pixel ratio 1).
- Full-page implementation: `/private/tmp/roxy-nexo-fix.1La6Ve/artifacts/pet-passport-mobile-v134.png` (390 × 2154 px).
- Side-by-side comparison: `/private/tmp/roxy-nexo-fix.1La6Ve/artifacts/pet-passport-reference-vs-v134.png` (800 × 892 px). The source was normalized to 390 px wide; the implementation remained at its native 390 px width.
- State: authenticated local QA profile for Bella, young Bernese Mountain dog, 70% profile completion, four daily routines, one weight record, no profile photo.

## Full-view comparison

The new screen follows the reference's passport hierarchy: large circular identity area, serif pet name, visible profile progress, veterinary share action, four primary destinations, weekly strip, daily timeline and emphasized next action. Roxy Home's multi-pet selector remains above the passport intentionally because it is required to switch between saved animals. The test profile intentionally uses the real no-photo fallback; production profiles continue to render their saved photo in the same circular frame.

## Focused-region comparison

The identity/progress region and the four-tab navigation were checked at 390 px after the first QA pass. The first pass exposed an overlap between the wrapped title, breed and profile progress. The final capture shows these elements separated, readable and aligned. The weekly strip and beginning of the daily timeline are visible above the persistent navigation without horizontal overflow.

## Required fidelity surfaces

- Fonts and typography: Georgia display type and compact sans-serif labels reproduce the editorial passport hierarchy; the two-line pet name, metadata and progress remain readable at 390 px.
- Spacing and layout rhythm: the circular portrait, progress, veterinary share action, four equal tabs and weekly card use the reference's visual cadence. The multi-pet selector is an intentional product extension.
- Colors and visual tokens: cream canvas, forest green, white surfaces and restrained gold accents stay within the existing Roxy Home identity.
- Image quality and asset fidelity: saved pet photos render as real cropped images; the QA profile had no image and therefore correctly displayed the existing Material Symbols fallback rather than a fabricated pet photo.
- Copy and content: labels are concise and task-based—Resumen, Alimentación, Salud and Documentos—and personalized with the saved pet name, breed, life stage, food plan and medical records.

## Interaction and runtime checks

- Resumen, Alimentación, Salud and Documentos each reached a selected tab state in the in-app browser.
- The summary links preserve access to species-filtered recipes and product recommendations.
- No browser warnings or errors were recorded in the final pass.
- `node --check assets/roxy_list.js` passed.
- 33 Home list/family tests passed.

## Comparison history

- First pass P1: pet name, breed and progress overlapped on the mobile breakpoint.
- Fix: increased the identity block height, moved the progress region below metadata and simplified the active weekday label.
- Second pass P2: the reference's veterinary sharing action was missing from the passport header.
- Fix: added a dedicated `Compartir con veterinario` action using the saved profile and recent medical history.
- Post-fix evidence: `/private/tmp/roxy-nexo-fix.1La6Ve/artifacts/pet-passport-reference-vs-v134.png`; no actionable P0/P1/P2 issue remains.

final result: passed

---

# Multispecies pet care design QA

## Evidence

- Mobile render for an axolotl profile: `/private/tmp/roxy-nexo-fix.1La6Ve/.playwright-cli/page-2026-09-01T19-24-19-834Z.png` (390 × 844 px).
- Browser profiles tested: Milo (adult domestic ferret) and Azul (adult axolotl in a cycled aquarium).

## Behavior verified

- The pet selector changes the full care plan rather than only changing the displayed species name.
- Ferret care prioritizes species-specific commercial nutrition, heat safety, supervised exercise, compatibility and exotic-vet warning signs.
- Axolotl care switches the recipe label to “Alimentación” and prioritizes water quality, temperature, limited handling, aquatic maintenance and species isolation.
- The new care-first navigation remains readable with four tabs at 390 px.
- Profiles support dogs, cats, ferrets, rabbits, guinea pigs, hamsters, other small mammals, birds, fish, reptiles, amphibians, invertebrates, farm pets and a free-form other-species path.
- When no verified product matches an exact species, the interface says so instead of inventing a brand.

## Validation

- `node --check assets/roxy_list.js` passed.
- 44 Home list/family/food tests passed.

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

---

# Módulo Mascotas separado · design QA

## Comparación visual

- Fuente de verdad: referencia seleccionada por Roberto (`1-Photo-1.jpg`).
- Implementación: `reports/qa/roxy-pets-v125-mobile.png` a 390 × 844.
- Comparación conjunta: `reports/qa/roxy-pets-comparison.png`.

## Criterios verificados

- **Jerarquía:** perfil y nombre de mascota antes de las acciones; el siguiente cuidado domina el flujo.
- **Densidad:** solo la acción inmediata está abierta; rutina y guía se consultan bajo demanda.
- **Navegación:** cinco categorías caben en una fila; Mascotas queda centrado en la barra inferior junto a Jardín.
- **Consistencia:** crema, verde bosque y acentos dorados conservan la identidad de Roxy Home.
- **Legibilidad móvil:** títulos, botones y estados no se cortan a 390 px.
- **Separación conceptual:** Recetas familiares y Mascotas son destinos distintos.
- **Interacción:** pestañas, desplegables, navegación y registro de cuidado validados en navegador real.
- **Consola:** sin errores ni advertencias durante el recorrido.

Final result: passed
