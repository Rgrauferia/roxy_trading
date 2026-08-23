# Design QA — Plan de comidas v61

## Source visual truth

- User reference: `/tmp/codex-remote-attachments/01a00902-6774-7450-965e-15f74386c916/5827DB94-BDF8-4293-A447-F9D4F1802150/1-Photo-1.jpg`
- Requested change: remove the people, maximum-time and weekly-budget band completely.
- Implementation capture: `/tmp/roxy-home-v61-band-removed.png`
- Combined comparison: `/tmp/roxy-home-v61-remove-band-comparison.jpg`
- Viewport: 390 × 844 CSS pixels (mobile Safari/iPhone class).
- Source pixels: 1280 × 513; focused crop supplied by the user.
- Implementation pixels: 390 × 844; captured at the target CSS viewport. Density was normalized in the combined comparison.
- State: “Poco tiempo” selected, current day expanded, optional account modal closed.

## Full-view comparison evidence

- [x] The removed band is absent, including its background, icons, labels and spacing.
- [x] The weekly objective follows the lifestyle cards directly.
- [x] The current day and its meals move upward without overlapping the fixed navigation.
- [x] Header, lifestyle cards, objective, daily plan and bottom navigation retain the Roxy Home identity.

## Focused-region evidence

- [x] The exact source region containing “2 personas”, “25 min máximo” and the weekly budget no longer renders.
- [x] No blank placeholder remains where the region existed.
- [x] Automatic planning still derives household size, time and budget internally so removing the controls does not disable plan generation.

## Findings and comparison history

1. Initial review: the summary band added unnecessary density before the weekly objective.
2. v61 implementation: removed the full `meal-plan-limits` DOM block and its responsive CSS.
3. Final comparison: the objective becomes the next visual section, matching the user’s requested hierarchy.

## Interaction and runtime QA

- [x] Lifestyle selection remains interactive and drives plan generation.
- [x] Quick mode continues enforcing a 20-minute maximum automatically.
- [x] Existing household/profile preferences remain available to the planning engine.
- [x] JavaScript syntax check passes.
- [x] 95 targeted Roxy Home tests pass.
- [x] Browser console errors at the validated state: none.

final result: passed

---

# Design QA — Roxy Calendar v62

## Source visual truth

- User reference: `/tmp/codex-remote-attachments/01a00902-6774-7450-965e-15f74386c916/99106126-F08D-447E-B569-A511C4B0EB89/1-Photo-1.jpg`
- Implementation capture: `/tmp/roxy-calendar-v62-390x844.png`
- Combined comparison: `/tmp/roxy-calendar-comparison-v62.jpg`
- Viewport: 390 × 844 CSS pixels (mobile Safari/iPhone class).
- Source pixels: 590 × 1280, normalized to the target viewport for comparison.
- State: Calendar “Hoy” view, authenticated private member, realistic Home and Family events, dialogs closed.

## Full-view comparison evidence

- [x] Calendar is a first-class bottom-navigation destination and replaces “Más”.
- [x] Header, green-and-cream palette, serif hierarchy, gold accent, Roxy portrait and generous touch targets retain the Roxy Home identity.
- [x] The hero, voice action, seven-day strip and chronological agenda follow the supplied composition without copying third-party branding.
- [x] The 390 px mobile viewport has no horizontal layout overflow or clipped headings.
- [x] The floating add button is hidden on narrow screens because each agenda-day header already provides an accessible “+” control.

## Focused-region evidence

- [x] “Tu semana, organizada” remains a clean two-line heading at iPhone width.
- [x] The Roxy voice button fits completely and opens the existing compact voice panel.
- [x] Event rows expose time, category icon, title, location/calendar and reminder without overlapping the bottom navigation.
- [x] Empty states and category colors remain readable and do not depend on color alone.

## Findings and comparison history

1. Initial build: the hero title wrapped into four lines and the mobile floating “+” overlapped agenda content.
2. First refinement: reduced the mobile hero side column, resized the portrait, widened the voice button inward and used the day-header add control.
3. Functional QA found that class `display` rules overrode the native `hidden` attribute, causing Month and Week content to appear together.
4. Final refinement added explicit hidden-state rules; Today, Week, Month and Year now render exclusively.
5. Final combined comparison confirms a faithful Roxy-specific implementation with clearer sync wording than the reference’s unverified “iPhone conectado”.

## Interaction and runtime QA

- [x] Manual event creation opens a complete form and requires a second confirmation before persistence.
- [x] Today, Week, Month and Year switch independently.
- [x] The compact Roxy voice surface opens from “Agregar hablando”.
- [x] Existing events open in edit mode with delete and “Agregar al iPhone” `.ics` export actions.
- [x] Browser console warnings/errors at the validated state: none.
- [x] JavaScript syntax check and the complete Home test suite pass.

final result: passed
