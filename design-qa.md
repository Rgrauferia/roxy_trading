# Nexo mobile design QA

- Reference fidelity: map-first composition, live context strip, private household selector, portrait rail, personal status card, and departure guidance follow the approved visual direction while preserving Roxy Home typography and colors.
- Responsive check: verified at 390 × 844 and desktop width. Controls remain reachable, the map is dominant, and the lower presence sheet reads as a separate layer.
- Empty state: verified without household members; copy is centered, readable, and points to the next action.
- Interaction: weather, map layers, locate, permanent sharing, profile selection, route guidance, trusted invitations, and privacy settings use real application state rather than decorative placeholders.
- Data honesty: numeric device battery appears only when an authorized backend provides it. The web version never fabricates a percentage and explains the native-app/Home Assistant requirement.
- Accessibility: semantic buttons, visible labels, aria-live status regions, descriptive map controls, and large mobile targets are retained.
- Browser QA: no new JavaScript runtime errors after navigation and pageshow/visibility re-entry testing. Expected local 401 remains because the isolated QA server has no account session.

final result: passed
