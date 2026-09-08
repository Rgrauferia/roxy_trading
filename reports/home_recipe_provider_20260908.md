# Human recipe provider boundary — 2026-09-08

## Candidate 177 follow-up (not proof of production activation)

Roberto confirms he has no account or API key. No purchase, account creation,
commercial license approval, environment change or production activation occurred.
New explicit human-only endpoints list cuisines and fetch up to four complete
records for a selected cuisine. The frontend offers a load-countries button and
discards stale responses after query/user changes. Local Wikibooks originals are
a separate free source and never use the TheMealDB development key.

One development-only request to the official documented key-1 search endpoint
returned HTTP200: id52771, Spicy Arrabiata Penne, Italian, eight ingredients,
619 instruction characters and a photo URL. Its CC flag was null. No recipe or
image from that probe was published, stored in a household, copied to the open
catalog, or treated as licensed. This checks the live response shape only;
production access and per-item rights still require verification.

The official API page currently routes signup through PayPal whereas its FAQ
requires commercial-tier Patreon support. Do not infer a commercial license from
the homepage's one-off price. The API page publishes thedatadb (at) gmail.com for
clarification. No message has been sent. Confirm intended web+App Store usage,
recipe/photo reuse, translations, caching and final recurring/one-off cost before
payment or flags. Store any resulting private key only in Home server secrets.

## Actual state

The new `roxy_os/home_recipe_provider.py` adapter is implemented but disabled by
default. No account, commercial license, payment or API call was made. Existing
recipe-provider credentials were not found in the local environment; production
configuration was not inspected. An enabled configuration is not a live check.

This is a human-food source, never a veterinary recipe source. It does not import
content into households or the shared SQLite library, generate with AI, translate,
or call the provider during availability checks.

## Callable contract

- `HomeRecipeProviderConfig.from_env()` reads only the Home variables below.
- `recipe_provider_availability(config=None)` returns a sanitized public summary.
- `search_provider_recipes(query, *, audience="human", limit=12, config=None,
  transport=None)` returns a tuple of immutable `ProviderRecipe` records.
- `get_provider_recipe(provider_id, *, audience="human", config=None,
  transport=None)` returns one immutable record or `None` for no match. Invalid
  content raises `RecipeProviderContentError`; configuration/network failures use
  sanitized `RecipeProviderUnavailable` messages.
- `.to_dict()` returns independent JSON containing `provider_original`, original
  English instructions, source-ordered paragraph steps, exact ingredient measure
  strings and attribution. Quantity/unit and servings stay `None`: the source
  does not supply reliable structured servings. Display provider text as text,
  never unsanitized HTML or executable instructions.

Do not send these records through `HomeFoodStore._normalize_recipe`, the shared
recipe publisher, or the local category editorializer. Conversion into a saved
Roxy recipe needs reviewed quantities, servings, translation, photo correspondence
and source rights. `can_cook`/`can_add_to_shopping` remain false; provider content
does not acquire an automatic verified status.

## Configuration proposed, not set

`ROXY_HOME_RECIPE_PROVIDER_ENABLED`, `ROXY_HOME_THEMEALDB_API_KEY`,
`ROXY_HOME_THEMEALDB_COMMERCIAL_LICENSE_CONFIRMED`,
`ROXY_HOME_RECIPE_PROVIDER_TIMEOUT_SECONDS`,
`ROXY_HOME_RECIPE_PROVIDER_MAX_RESULTS`,
`ROXY_HOME_THEMEALDB_LICENSED_RECIPE_IDS`.

Both opt-in flags and a non-test key are required. Key `1`, placeholder keys and
non-human audiences cannot make requests. API-key URLs stay server-side; HTTP
redirects are disabled and errors never expose response bodies or secret URLs.
Requests use bounded timeouts/deadlines, a 512 KiB body cap, at most 100 records
examined and at most 20 returned (default 12). No retries or background downloads.

External recipe/image provenance requires the operator's per-ID rights allowlist,
backed by documented rights to BOTH recipe and photo. Records attributed only to
TheMealDB can pass the initial provenance boundary with its CC artwork marker;
they still require editorial/photo review. Missing instructions, measures, photos
or rights never become ready recipes. The adapter only accepts images on the
provider's meal-image paths. It does not assume an arbitrary source image is free.

## Official-source research and limits

- [TheMealDB terms](https://www.themealdb.com/terms_of_use.php) permit copying and
  modifying official API responses, with attribution and third-party rights
  restrictions. App Store distribution requires paid access. Its
  [FAQ](https://www.themealdb.com/faq.php) calls for commercial-tier support.
  [Homepage](https://www.themealdb.com/) advertises $10 one-off while the
  [guide](https://www.themealdb.com/docs_api_guide.php) elsewhere says £10;
  confirm commercial terms/cost before enabling. The
  [schema](https://www.themealdb.com/api/spec/openapi-v1.yaml) has nullable
  instructions, image/source/CC metadata and 20 ingredient/measure pairs, but no
  guaranteed Spanish field or structured servings. It is crowd-sourced, not a
  promise that every recipe has been professionally tested.
- [Spoonacular terms](https://spoonacular.com/food-api/terms) prohibit persistent
  ingredient/instruction storage and transformed copies; ID/title/image URL are
  exceptions, and up to one hour of caching requires prior written permission.
  [Published plans](https://spoonacular.com/food-api/pricing) start at 50 free
  points/day or $29/month for 1,500/day with overages. Standard content is English.
  This is not a drop-in source for Roxy's indefinitely stored shared recipes.
- [Edamam plans](https://developer.edamam.com/edamam-recipe-api): $9/$99 web-recipe
  plans do not supply cooking instructions. The $399/month owned-content tier
  includes them, but attribution and caching restrictions still apply. A
  [content license](https://developer.edamam.com/recipe-database-licensing) is a
  more explicit production option if the budget/rights are approved.
- [Nutrition.gov](https://www.nutrition.gov/recipes) and the
  [2024 bilingual NHLBI cookbook](https://www.nhlbi.nih.gov/resources/delicious-heart-healthy-latino-recipes-book-platillos-latinos-sabrosos-y-saludables)
  are possible curated seed sources without API credentials. Per-item text/image
  rights must be checked; not all government-hosted photos are public domain.
  [USDA policy](https://www.usda.gov/about-usda/policies-and-links) has third-party
  exceptions; [NHLBI policy](https://www.nhlbi.nih.gov/about/contact/trademark-branding-and-logo)
  restricts alteration of formatted multimedia and implied endorsement.

## Verification

49 dedicated synthetic tests passed (0.15 s). They exercise opt-in gates, independent products, content and
rights rejection, source preservation, immutability, absent quantities/servings,
timeout/body/result bounds, malformed URLs/payloads, sanitized errors and absence
of pet calls. No live recipes downloaded, subscriptions created or fees incurred.
Production integration and licensing remain pending.

## Server integration completed locally, not activated

The authenticated Home service now exposes these GET-only routes:

- `/v1/home-food/{user_id}/providers/recipes/status`: sanitized configuration,
  no external call and no household/library access.
- `/v1/home-food/{user_id}/providers/recipes/search?q=egg&limit=12&requested=true`:
  deliberate human-only search, at most 20 returned records.
- `/v1/home-food/{user_id}/providers/recipes/{provider_id}?requested=true`:
  original record for review; 404 for no match, 422 for rejected content.

The ordinary Home snapshot includes the same state under
`recipe_provider_service`. `available` means configured with operator-confirmed
license, **not** live verified. `access_allowed` is additionally false for trial
sessions and `access_status` explains `not_included_in_demo`. Status is an exact
GET-only exception in the demo's route allowlist; search and detail remain
blocked until a separate external-recipe allowance is approved. Expired trials
may read configuration but cannot invoke the provider. No demo quota is charged
by this read-only status check.

Household authorization precedes provider access; normal private/no-store response
headers apply. The provider receives only the deliberately entered search phrase
or recipe ID, never pet profiles, allergies, household IDs, pantry or chat history.
There is no save/import/translation/media-generation side effect, and unavailable
providers never fall back to a random chicken recipe. The `.env.example` documents
the Home-only flags and blank key; actual environments were not modified.

89 provider/HTTP tests and 15 public-demo tests passed together (104 total,
2.98 s). In addition to the adapter contracts, tests exercise signed household
sessions, real synthetic active/expired trial accounts, status without network,
original-data preservation, deliberate-request and input-validation gates,
sanitized errors, no private store mutations and no-store responses. These are
synthetic tests, not a commercial connection or licensing verification. No fees,
account changes or paid provider requests were made.

Activation still requires confirmation of the final commercial price, written
recipe/image reuse rights for the intended web/App Store behavior, a Home-only
paid key, an explicit usage budget, and a deliberately requested live smoke test.
Do not enable from the publicly documented development key or infer that the
user's permission to prepare the integration authorizes a purchase.
