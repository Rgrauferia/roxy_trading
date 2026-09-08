"""Recipe navigation must not confuse an unanswered/negative profile with deletion."""
from copy import deepcopy
from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_food import HomeFoodStore, RecipeReviewRequired
from roxy_os.home_pet_capabilities import pet_capabilities
from roxy_os.home_pet_catalog import COMMON_CONDITIONS, PRODUCTS
from roxy_os.home_pet_product_safety import product_safety
from roxy_os.home_pet_restrictions import has_medical_restrictions
from roxy_os.home_recipe_fallback import personalized_pet_recipe_catalog


@pytest.mark.parametrize("species,answer", [(species, answers[0]) for species, answers in COMMON_CONDITIONS.items()])
def test_every_no_condition_choice_offered_by_profile_is_an_exact_negative(species, answer):
    assert answer in {"Ninguna diagnosticada", "Ninguna observada"}
    assert not has_medical_restrictions({"species": species, "conditions": [answer]})
    assert has_medical_restrictions({"species": species, "conditions": [answer, "Tratamiento activo"]})
    assert has_medical_restrictions({"species": species, "conditions": [answer + " salvo diabetes"]})


@pytest.mark.parametrize("species,exact,count", [
    ("dog", "Bernese Mountain", 15), ("cat", "Maine Coon", 12), ("ferret", "Ferret", 8),
    ("rabbit", "Conejo doméstico", 3), ("guinea_pig", "Cobaya", 3),
    ("hamster", "Hámster sirio", 3), ("bird", "Periquito australiano", 3), ("bird", "Canario", 3),
])
def test_profile_with_real_questionnaire_negative_restores_only_its_own_preparations(species, exact, count):
    pet = {"id": "qa", "name": "Prueba", "species": species, "breed": exact, "exact_species": exact,
           "life_stage": "young" if species == "dog" else "adult", "conditions": ["Ninguna diagnosticada"], "allergies": ["Ninguna conocida"]}
    rows = personalized_pet_recipe_catalog(pet, {})
    assert len(rows) == count
    capability = pet_capabilities(pet, rows)
    assert capability["recipe_tab"] and capability["recipes"] and capability["recipe_import"]
    assert capability["recipe_count"] == count and capability["recipe_status"] == "available"
    assert all(row["pet_id"] == pet["id"] and row["pet_species"] == species and row["photo_asset_verified"] for row in rows)
    assert all(row["safety_class"] in {"treat", "complement"} for row in rows)


@pytest.mark.parametrize("change", [
    {"conditions": ["Insulinoma"]}, {"conditions": ["Ninguna diagnosticada", "Insulinoma"]},
    {"conditions": ["Ninguna salvo diabetes"]}, {"current_food_kind": "veterinary"},
    {"veterinarian_instructions": "No cambiar su dieta"}, {"allergies": ["Otra"]},
    {"life_stage": "unknown"}, {"life_stage": "baby"},
])
def test_blocked_ferret_keeps_explanation_tab_without_cooking_or_import_permission(change):
    pet = {"id": "luna", "name": "Luna", "species": "ferret", "life_stage": "adult", **change}
    rows = personalized_pet_recipe_catalog(pet, {})
    capability = pet_capabilities(pet, rows)
    assert rows == []
    assert capability["recipe_tab"] and "recipes" in capability["tabs"]
    assert not capability["recipes"] and not capability["recipe_import"]
    assert capability["recipe_status"] == "profile_review_required"
    assert capability["recipe_notice"] and capability["recipe_notice_title"]


@pytest.mark.parametrize("species,exact", [
    ("fish", "Betta"), ("reptile", "Pitón bola"), ("bird", "Lori arcoíris"),
    ("bird", "No sé"), ("amphibian", "Ajolote"), ("invertebrate", "Tarántula"),
    ("farm_pet", "Caballo"), ("small_mammal", "Chinchilla"), ("other", "No sé"),
])
def test_specialist_species_still_have_no_recipe_tab(species, exact):
    pet = {"id": "qa", "species": species, "exact_species": exact, "life_stage": "adult", "conditions": ["Ninguna diagnosticada"]}
    capability = pet_capabilities(pet, personalized_pet_recipe_catalog(pet, {}))
    assert not capability["recipe_tab"] and not capability["recipes"] and not capability["recipe_import"]
    assert "recipes" not in capability["tabs"] and capability["recipe_notice"]


def test_empty_or_wrong_pet_shelf_is_not_an_authorization_to_import():
    pet = {"id": "one", "name": "Ferret", "species": "ferret", "life_stage": "adult"}
    rows = personalized_pet_recipe_catalog(pet, {})
    for other, shelf in ((pet, []), ({**pet, "id": "two"}, rows)):
        capability = pet_capabilities(other, shelf)
        assert capability["recipe_tab"] and not capability["recipe_import"]
        assert capability["recipe_status"] == "no_matches" and capability["recipe_count"] == 0


def test_negative_answer_does_not_block_food_but_real_condition_still_does():
    product = next(row for row in PRODUCTS["ferret"] if row["brand"] == "Oxbow")
    pet = {"species": "ferret", "conditions": ["Ninguna diagnosticada"], "allergies": ["Ninguna conocida"]}
    assert not product_safety(pet, product)["cart_blocked"]
    assert product_safety({**pet, "conditions": ["Insulinoma"]}, product)["cart_blocked"]


def test_restriction_does_not_delete_saved_recipe_or_profile_and_server_still_blocks(tmp_path):
    path = tmp_path / "home.json"
    store = HomeFoodStore(path)
    pet = store.upsert_pet("qa", name="Luna", species="ferret", life_stage="adult", conditions=["Ninguna diagnosticada"], photo_data_url="data:image/png;base64,PHOTO")
    recipe = store.save_recipe("qa", personalized_pet_recipe_catalog(pet, {})[0])
    store.upsert_pet("qa", name="Luna", species="ferret", pet_id=pet["id"], conditions=["Insulinoma"])
    snapshot = store.snapshot("qa")
    before = path.read_bytes()
    restricted = snapshot["pets"][0]
    assert restricted["photo_data_url"] == pet["photo_data_url"]
    assert not personalized_pet_recipe_catalog(restricted, snapshot)
    assert pet_capabilities(restricted, [recipe])["recipe_tab"]
    for action in (store.start_cooking_session, store.shopping_preview):
        with pytest.raises(RecipeReviewRequired):
            action("qa", recipe["id"])
    assert path.read_bytes() == before
    assert snapshot["recipes"][0]["id"] == recipe["id"]


def test_api_real_questionnaire_answer_keeps_luna_and_bella_and_all_luna_photos(tmp_path, monkeypatch):
    from tools import roxy_home_service as service
    monkeypatch.setenv("ROXY_HOME_API_KEY", "qa-pet-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "qa")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_RECIPE_IMAGE_GENERATION_ENABLED", "0")
    monkeypatch.setattr(service, "_schedule_account_recipe_photo", lambda *args, **kwargs: None)
    service._RATE_STATE.clear()
    store = service._home_food_store()
    bella = store.upsert_pet("qa", name="Bella", species="dog", life_stage="young", breed="Bernese Mountain", conditions=["Ninguna diagnosticada"])
    luna = store.upsert_pet("qa", name="Luna", species="ferret", exact_species="Ferret", life_stage="adult", conditions=["Ninguna diagnosticada"], photo_data_url="data:image/png;base64,LUNA")
    before = deepcopy(store.snapshot("qa")["pets"])
    client = TestClient(service.app)
    response = client.get("/v1/home-food/qa", headers={"Authorization": "Bearer qa-pet-key"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pets"] == before == store.snapshot("qa")["pets"]
    assert {row["id"] for row in body["pets"]} == {bella["id"], luna["id"]}
    rows = body["pet_recipe_recommendations"][luna["id"]]
    assert len(rows) == len({row["photo_asset"] for row in rows}) == 8
    assert body["pet_capabilities"][luna["id"]]["recipe_count"] == 8


def test_client_blocked_section_explains_reason_and_edits_without_mutating():
    source = (Path(__file__).resolve().parents[1] / "assets/roxy_list.js").read_text()
    function = source.split("  function renderPetRecipeAvailability(", 1)[1].split("  function openPetHubSection(", 1)[0]
    script = """
const assert=require('node:assert/strict');
const make=()=>({children:[],attrs:{},listeners:{},append(...items){this.children.push(...items)},setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v){this.listeners[k]=v}});
const document={createElement:make};const nodes={recipeFilters:{},recipeSearch:{},recipeCount:{}};const $=id=>nodes[id];
let edited=null;const openPetProfile=pet=>edited=pet;let capability;const petCapabilities=()=>capability;
""" + "function renderPetRecipeAvailability(" + function + """
const pet={id:'luna',name:'Luna',species:'ferret'};let root=make();
capability={recipes:false,recipe_notice:'Confirma su etapa de vida.',recipe_notice_title:'Revisar perfil'};
assert.equal(renderPetRecipeAvailability(pet,root),true);
assert.equal(nodes.recipeSearch.disabled,true);assert.equal(nodes.recipeFilters.hidden,true);
assert.equal(root.children[0].children[1].textContent,capability.recipe_notice);
const button=root.children[0].children.find(row=>row.listeners.click);button.listeners.click();assert.equal(edited,pet);
root=make();capability={recipes:true,recipe_notice:'Premio ocasional, no dieta completa.',recipe_source:{url:'https://hospital.cvm.ncsu.edu/',label:'Orientación veterinaria'}};
assert.equal(renderPetRecipeAvailability(pet,root),false);
assert.equal(root.children[0].children.at(-1).href,capability.recipe_source.url);
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_ferret_sources_are_not_presented_as_certification_of_our_preparation():
    pet = {"id": "qa", "name": "Luna", "species": "ferret", "life_stage": "adult"}
    rows = personalized_pet_recipe_catalog(pet, {})
    for row in rows:
        assert "las fuentes no certifican esta receta" in row["canonical_variant"]
        assert row["content_revision"] == "ferret-preparation-2026-09-08"
        assert "no la ración" in row["veterinary_note"]
        assert row["steps"][-1].startswith("Guarda pronto")
        assert "1 hora" in row["steps"][-1] and "32 °C" in row["steps"][-1]
    duck = next(row for row in rows if row["catalog_key"] == "ferret_baked_duck")
    assert "190 °C" in " ".join(duck["steps"]) and "termómetro" in " ".join(duck["steps"])
    assert "74 °C" in " ".join(duck["steps"])


def test_pet_selection_chips_report_their_active_state_to_assistive_technology():
    source = (Path(__file__).resolve().parents[1] / "assets/roxy_list.js").read_text()
    function = source.split("  function renderPetChoices(", 1)[1].split("  function ", 1)[0]
    script = """
const assert=require('node:assert/strict');
const make=()=>{const active=new Set();return {children:[],dataset:{},attrs:{},listeners:{},
classList:{toggle(k,v){v=v===undefined?!active.has(k):v;v?active.add(k):active.delete(k)},contains:k=>active.has(k),add:k=>active.add(k),remove:k=>active.delete(k)},
append(...items){this.children.push(...items)},replaceChildren(){this.children=[]},querySelectorAll(){return this.children},
setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v){this.listeners[k]=v}}};
const root=make();const document={createElement:make};const $=()=>root;const normalize=value=>value.toLowerCase();
""" + "function renderPetChoices(" + function + """
renderPetChoices('conditions',['Ninguna diagnosticada','Insulinoma'],['Ninguna diagnosticada']);
const [none,condition]=root.children;
assert.equal(none.attrs['aria-pressed'],'true');assert.equal(condition.attrs['aria-pressed'],'false');
condition.listeners.click();assert.equal(none.attrs['aria-pressed'],'false');assert.equal(condition.attrs['aria-pressed'],'true');
none.listeners.click();assert.equal(none.attrs['aria-pressed'],'true');assert.equal(condition.attrs['aria-pressed'],'false');
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
