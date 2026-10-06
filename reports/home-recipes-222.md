# Home222 — recover MyPlate catalog after image-host change

Observed public Explore failed. A focused provider probe reproduced HTTP422
invalid_content even though the upstream search returned200. MyPlate changed
image_url from its Google Storage bucket to recipe-images.myplate.food.
Roxy's old image allowlist correctly failed closed, rejecting every affected
recipe summary. Updated server and browser validators and page CSP only for
HTTPS recipe-images.myplate.food/recipe-images/<safe-name>.(jpg|jpeg|png|webp).
Legacy bucket remains supported. Queries, credentials, other paths/hosts/ports,
SVG and redirects remain disallowed. No generic replacement photo is added.

Regression: accepted new image domain in search and detail; preserved original
ingredients and directions; rejected spoofed domains, paths, query strings,
credentials, ports and active media. CSP check covers the exact new path.

Live low-volume probe:24 summaries accepted, total1072 reported by the source.
One complete recipe opened with4 ingredients and7 literal reading segments;
concatenation equals the original directions. This is NOT individual review of
1072 recipes, bulk import, or a license to mirror the source. Attribution and
existing on-demand guide/translation/privacy rules remain intact.

Official docs checked2026-10-06: https://myplate.food/api . Independent service,
not the official USDA API. Commercial live per-request use permitted;20 requests
per minute/IP,100 full recipes per day/IP. No bulk copy or quota bypass.

Verification:489 Python tests and348 Node tests passed; JS syntax and diff checks.
HTML/APP222, main JS230, MyPlate JS10, SW222; CSS144 unchanged.
Includes Home220 reliability and Home221 visible loading/retry fixes.
End-to-end production verification recorded in Home continuity after deployment.
