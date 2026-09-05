"""Isolated local QA home. No production accounts, pets, credentials or AI calls."""
import os
from pathlib import Path
import tempfile

import uvicorn


def main():
    directory = Path(tempfile.mkdtemp(prefix="roxy-pets-qa-"))
    os.chdir(directory)
    # Never inherit production storage paths, provider settings or account state.
    for key in list(os.environ):
        if key.startswith("ROXY_"):
            os.environ.pop(key)
    os.environ.update(ROXY_HOME_API_KEY="local-pets-qa-only", ROXY_STATE_SYNC_USERS="qa",
                      ROXY_HOME_RECIPE_IMAGE_GENERATION_ENABLED="0", ROXY_HOME_RECIPE_VIDEO_ENABLED="0")
    # Remove inherited provider credentials from this local test process only.
    for key in list(os.environ):
        if "OPENAI" in key or key.endswith("_API_KEY") and key != "ROXY_HOME_API_KEY":
            os.environ.pop(key)
    from roxy_os.home_food import HomeFoodStore
    from roxy_os.home_accounts import HomeAccountStore
    from tools import roxy_home_service as service
    HomeAccountStore("data/roxy_home_accounts.json").bootstrap("qa", household_name="Pruebas locales", username="petsqa", display_name="Prueba", password="LocalPetsQA-2026!")
    store = HomeFoodStore("data/roxy_home_food.json")
    for name, species, exact in [("Ave QA", "bird", "Periquito australiano"), ("Acuario QA", "fish", "Betta splendens"), ("Terrario QA", "reptile", "Gecko leopardo"), ("Ferret QA", "ferret", "Hurón doméstico"), ("Canario QA", "bird", "Canario"), ("Lori QA", "bird", "Lori arcoíris")]:
        store.upsert_pet("qa", name=name, species=species, exact_species=exact, life_stage="adult")
    print(f"Temporary QA data: {directory}", flush=True)
    uvicorn.run(service.app, host="127.0.0.1", port=8767, access_log=False)


if __name__ == "__main__":
    main()
