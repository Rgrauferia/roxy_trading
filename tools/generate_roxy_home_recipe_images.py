#!/usr/bin/env python3
"""Generate exact Roxy Home recipe images once with the Responses API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from roxy_os.home_ai import HomeAIConfig
from roxy_os.home_recipe_catalog import installed_recipe_templates
from roxy_os.home_recipe_photos import RecipePhotoStore, recipe_photo_prompt


def _image_result(response) -> str:
    for item in response.output:
        if getattr(item, "type", "") == "image_generation_call" and getattr(item, "result", None):
            return str(item.result)
    raise RuntimeError("OpenAI no devolvió una imagen")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", action="append", help="Título exacto; puede repetirse")
    parser.add_argument("--category", help="Generar solo una categoría instalada")
    parser.add_argument("--limit", type=int, default=10, help="Máximo por ejecución")
    parser.add_argument("--quality", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--approve", action="store_true", help="Publicar inmediatamente tras generar")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 50:
        parser.error("--limit debe estar entre 1 y 50")

    config = HomeAIConfig.from_env()
    client = OpenAI(api_key=config.api_key)
    store = RecipePhotoStore()
    requested = {title.casefold() for title in (args.title or [])}
    recipes = [
        recipe for recipe in installed_recipe_templates().values()
        if (not requested or str(recipe["title"]).casefold() in requested)
        and (not args.category or recipe.get("category") == args.category)
        and store.resolve(str(recipe["title"])) is None
    ][: args.limit]

    for recipe in recipes:
        title = str(recipe["title"])
        response = client.responses.create(
            model=config.routine_model,
            input=recipe_photo_prompt(recipe),
            tools=[{"type": "image_generation", "quality": args.quality, "size": "1024x1024"}],
            store=False,
        )
        store.save_generated(title, _image_result(response), approved=args.approve)
        print(f"{'Aprobada' if args.approve else 'Pendiente de revisión'}: {title}")
    print(f"Imágenes procesadas: {len(recipes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
