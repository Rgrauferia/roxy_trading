# Home 220 — reliability audit, 2026-10-06

Scoped release derived from public Home219 (6ddcf99). Does not include unfinished
Fitness218 or Pinterest work from other dirty checkouts.

## Implemented and tested

- Weekly menus rank compatible existing recipes by same-day avoidance, previous
  day avoidance and usage, instead of repeatedly selecting the first option.
  Time and registered allergy filters remain authoritative. No new recipes.
- Ingredient-ready state persists on the server, survives reload and excludes
  that day from shopping. Changing its recipe clears readiness; rescheduling
  moves it with the meals. Failed saves roll back the checkbox; late responses
  cannot update a different member. Shopping still requires confirmation.
- Explicit questions about Roxy's capabilities route to read-only conversation,
  not cooking or recipe generation. Explicit action routes remain intact.
- Text chat uses safe, actionable status messages, retains unsent text and does
  not reload the entire household after an informational answer.
- Old plans retain their stored dates. The interface offers creating a new week
  rather than silently relabeling historic meals as today.
- Version220 / JS228 / shell220 invalidate the previous application cache.

## Verification

236 Python tests passed (weekly domain/API, information intent, list/version,
conversation and budget storage). 342 Node tests passed (guide, open/MyPlate
catalog, conversation, exact save-and-cook, new readiness/date/error tests).
JavaScript syntax and git diff whitespace checks passed.

CUA isolated synthetic account on localhost8773: created seven days; marked
ingredients ready; reloaded and confirmed checked state; opened exact Avena con
manzana; saved and cooked steps1→2; closed without freeze. No provider credentials
in the fixture: its photo/audio absence is intentional, not production evidence.
Screenshots in Home working checkout reports/home-ipad-20261006 (09–13).

## Observed production limitations

- Official voice test returned HTTP503 / payment_issue from ElevenLabs. Existing
  Home credentials are configured, but billing blocks synthesis. No payment,
  credential substitution or unofficial voice activation performed.
- Sanitized OpenAI budget status: one successful request,118 output tokens on
  2026-10-06; no pending provider failure. A visible end-to-end chat answer must
  still be verified after release.
- Luna remains a Ferret. Eight occasional treats are pending review, not
  verified diets; this release does not bypass veterinary review.
- One transient public502 was observed; subsequent reload returned Roxy Home.
  Render also displays Payment failed. Neither a successful deploy nor these
  tests certify sustained uptime or every module.

## Muse / Dot

Official Meta Model API supports application integrations. MuseCode is a coding
agent, not a drop-in Home conversation service. The existing local Muse adapter
is only a sanitized technical reviewer. Muse Voice documented here is speech
transcription, not synthesis: it does not automatically replace Roxy's voice.
No Meta key, new permissions, shared memories or provider switch activated.
Roxy Dot remains unidentified pending the owner's clarification.

Sources: https://dev.meta.ai/docs/overview ; https://dev.meta.ai/docs/muse-code/auth
Preserve Roxy identity and product-isolated secrets, memory, permissions and
budgets for any future provider comparison.

Deployment verification is recorded in the Home continuity files after Live.
