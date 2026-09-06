"""Read-only, reproducible inventory. This is not culinary or veterinary approval."""
from collections import Counter
import json
from pathlib import Path

from roxy_os.home_recipe_fallback import local_recipe_catalog
from roxy_os.home_recipe_editorial import recipe_quality_issues


def audit_catalog():
    root = Path(__file__).resolve().parents[1]
    rows = local_recipe_catalog({})
    images = Counter(row.get("photo_asset") for row in rows if row.get("photo_asset"))
    records = []
    for recipe in rows:
        pet = recipe.get("audience") == "pet"
        guide = recipe.get("safety_class") == "feeding_guide"
        asset = recipe.get("photo_asset", "")
        problems = []
        if not recipe.get("ingredients") or not recipe.get("steps"):
            problems.append("missing_ingredients_or_steps")
        if asset and not (root / asset.lstrip("/")).is_file():
            problems.append("missing_local_asset")
        if not pet:
            problems.extend(recipe_quality_issues(recipe, recipe["title"]))
        records.append({
            "key": recipe["catalog_key"], "title": recipe["title"],
            "module": "pet_care" if guide else "pet_recipes" if pet else "human_recipes",
            "species": recipe.get("pet_species", ""),
            "editorial_status": recipe.get("editorial_status", "not_recorded"),
            "ingredient_count": len(recipe.get("ingredients", [])),
            "step_count": len(recipe.get("steps", [])),
            "local_photo": asset, "local_photo_exact_reviewed": bool(recipe.get("photo_asset_verified")),
            "asset_reuse_count": images.get(asset, 0),
            "checks": problems,
        })
    return {
        "scope": "All installed catalog rows; no account data or provider calls. Remote photo existence and visual correspondence need separate verification.",
        "total": len(records), "modules": dict(Counter(row["module"] for row in records)),
        "editorial_statuses": dict(Counter(row["editorial_status"] for row in records)),
        "rows_with_automated_findings": sum(bool(row["checks"]) for row in records),
        "recipes": records,
    }


if __name__ == "__main__":
    print(json.dumps(audit_catalog(), ensure_ascii=False, indent=2))
