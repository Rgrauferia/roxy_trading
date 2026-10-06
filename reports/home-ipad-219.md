# Home 219 — iPad meal-plan and cooking fixes

Scope: meal plan → exact recipe → guided cooking. Release derived only from
public cabd169; excludes unfinished Fitness218 and Pinterest adapter changes.

- Explicit “Guardar y cocinar con Roxy” saves the selected catalog_key, then
  opens a cooking session using the server-returned recipe id. Opening stays
  read-only; shopping still requires its separate confirmation.
- Catalog buttons disable while saving, preserving failure recovery.
- Guided steps reset scroll only on session/step/status changes.
- Fixed an observed browser freeze: invalid guide scope repeatedly suspended
  itself through MutationObserver-generated DOM writes. Suspension is now
  idempotent and re-arms when the scope becomes usable.
- Compact workspace surface, three meal cards in landscape at >=900px;
  single-column phone layout, >=44px recipe and action targets, correct chevrons.
- Installed name “Roxy Home”; orientation any, preserving start_url/scope.

Verification before publication: 55 Python tests;177 Node tests. CUA isolated
synthetic account8772: plan creation, catalog save-and-cook, exact steps1→2,
dialog scroll0, closing guide and selecting another day without freeze.
1180x820 and393x852: no horizontal overflow; phone recipe targets>=44px.
Offline QA deliberately has no provider credentials: photos and official
audio are unavailable there. No production household changes or purchases.
Evidence: reports/home-ipad-20261006 in the Home working checkout.

Limitations: does not expand the recipe catalog, remove plan repetition, or
certify all modules. Fitness218, its private database, and Guided Access on the
physical iPad remain separate work. Render billing warning requires the owner.
