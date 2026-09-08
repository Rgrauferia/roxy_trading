"""Concrete demo-readiness regressions, not a claim of clinical review."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess

import pytest

from roxy_os.home_aquarium import aquarium_assessment, validate_inhabitants
from roxy_os.home_family import HomeFamilyStore
from roxy_os.home_food import HomeFoodStore, HOME_COLLECTION_LIMITS
from roxy_os.home_pet_capabilities import pet_capabilities, pet_display_copy
from roxy_os.home_pet_catalog import EXACT_SPECIES, personalized_pet_care_plan
from roxy_os.home_pet_habitats import habitat_plan, validate_observations
from roxy_os.home_recipe_fallback import personalized_pet_recipe_catalog

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("species,exact", [(group, name) for group, names in EXACT_SPECIES.items() for name in names] + [("dog", "Bernese Mountain"), ("cat", "Maine Coon")])
def test_every_selectable_species_exposes_only_its_own_preparations(species, exact):
    pet = {"id": "isolated", "name": "QA", "species": species, "exact_species": exact, "life_stage": "adult"}
    recipes = personalized_pet_recipe_catalog(pet, {})
    capabilities = pet_capabilities(pet, recipes)
    assert capabilities["recipes"] == bool(recipes)
    assert capabilities["recipe_import"] == capabilities["recipes"]
    assert ("recipes" in capabilities["tabs"]) == bool(recipes)
    assert all(row["pet_id"] == pet["id"] and row["pet_species"] == species and row["safety_class"] != "feeding_guide" for row in recipes)
    if species in {"fish", "reptile", "amphibian", "invertebrate", "other", "farm_pet", "small_mammal"}:
        assert not recipes and capabilities["recipe_notice"]


def test_ferret_presentation_does_not_rename_saved_profile_or_artwork():
    pet = {"id": "luna", "name": "Luna", "species": "ferret", "exact_species": "Hurón doméstico", "life_stage": "adult"}
    before = deepcopy(pet)
    plan = pet_display_copy(pet, personalized_pet_care_plan(pet))
    assert "hurón" not in plan["information"]["characteristics"].lower()
    assert "Ferret" in plan["information"]["display_name"]
    raw = {"title": "Premio para hurón", "photo_asset": "/assets/huron.jpg", "source_url": "https://example.org/huron", "veterinary_note": "Para hurones"}
    shown = pet_display_copy(pet, raw)
    assert shown["title"] == raw["title"] and shown["photo_asset"] == raw["photo_asset"] and shown["source_url"] == raw["source_url"]
    assert "ferrets" in shown["veterinary_note"]
    assert pet == before


def test_recipe_tab_hides_for_medical_restriction_or_another_pets_shelf():
    pet = {"id": "luna", "name": "Luna", "species": "ferret", "life_stage": "adult"}
    recipes = personalized_pet_recipe_catalog(pet, {})
    assert pet_capabilities(pet, recipes)["recipes"]
    assert not pet_capabilities({**pet, "conditions": ["Insulinoma"]}, recipes)["recipes"]
    assert not pet_capabilities({**pet, "id": "other"}, recipes)["recipes"]


def test_aquarium_population_and_conflicts_are_saved_without_certifying_compatibility(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    pet = store.upsert_pet("qa", name="Acuario", species="fish", exact_species="Betta splendens")
    values = {"volume_l": 25, "residents": 2, "inhabitants": [
        {"species": "Betta splendens", "count": 2, "sex": "male", "adult_cm": 6},
        {"species": "Goldfish", "count": 1, "sex": "unknown", "adult_cm": ""},
    ]}
    store.record_pet_habitat("qa", pet["id"], values)
    updated = store.snapshot("qa")["pets"][0]
    assessment = aquarium_assessment(updated["habitat_observations"]["values"])
    assert assessment["count"] == 3 and assessment["status"] == "REVIEW_REQUIRED"
    assert any("dos machos" in text for text in assessment["alerts"])
    assert any("goldfish" in text for text in assessment["alerts"])
    assert any("total guardado" in text for text in assessment["alerts"])
    assert any("tamaño adulto" in text for text in assessment["alerts"])
    assert "no significa convivencia segura" in assessment["compatibility_note"]
    store.record_pet_habitat("qa", pet["id"], {"ph": 7})
    assert store.snapshot("qa")["pets"][0]["habitat_observations"]["values"]["inhabitants"] == assessment["inhabitants"]
    assert store.snapshot("other")["pets"] == []


@pytest.mark.parametrize("row", [[], {"species": "Betta", "count": 0}, {"species": "Betta", "count": True}, {"species": "Betta", "count": 1.5}, {"species": "Betta", "count": 1, "adult_cm": "NaN"}, {"species": "", "count": 1}, {"species": "Betta", "count": 1, "sex": "bad"}])
def test_invalid_population_is_rejected(row):
    with pytest.raises(ValueError):
        validate_inhabitants([row])


@pytest.mark.parametrize("species,exact", [(group, names[0]) for group, names in EXACT_SPECIES.items()])
def test_blank_optional_habitat_fields_do_not_crash_profile_reload(species, exact):
    pet = {"species": species, "exact_species": exact}
    fields = habitat_plan(pet)["questions"]
    values = {field["key"]: [] if field["kind"] == "inhabitants" else "" for field in fields}
    pet["habitat_observations"] = {"values": validate_observations(pet, values)}
    assert habitat_plan(pet)["sections"]


def test_snake_information_has_no_daily_homemade_recipe_plan():
    pet = {"species": "reptile", "exact_species": "Pitón bola", "life_stage": "adult"}
    plan = habitat_plan(pet)
    assert any("Serpientes: alimentación, no recetas" == row["title"] for row in plan["sections"])
    assert any("No se programa automáticamente una comida diaria" in row["text"] for row in plan["sections"])
    with pytest.raises(ValueError):
        validate_observations(pet, {"inhabitants": []})
    info = personalized_pet_care_plan(pet)["information"]
    assert "Python regius" in info["display_name"]
    assert "7–14 días" in info["frequency"] and "20 años" in info["life_expectancy"]
    assert "7–14" not in personalized_pet_care_plan({**pet, "life_stage": "baby"})["information"]["frequency"]


def test_exact_information_does_not_cross_species_or_claim_unknown_coverage():
    info = personalized_pet_care_plan({"species": "dog", "breed": "Maine Coon"})["information"]
    assert info["scope"] == "group" and "coverage_notice" in info
    unknown = personalized_pet_care_plan({"species": "reptile", "exact_species": "No sé"})["information"]
    assert "pendiente" in unknown["life_expectancy"]


def test_human_recipes_default_shelf_excludes_unreviewed_drafts():
    source = (ROOT / "assets/roxy_list.js").read_text()
    function = source[source.index("  function humanRecipeShelf("):source.index("  function petCapabilities(")]
    script = function + """
const rows=[{audience:'human',title:'Lista',editorial_status:'reviewed'},{audience:'human',title:'Borrador',editorial_status:'needs_canonical_review'},{audience:'pet',title:'Premio'}];
if(humanRecipeShelf(rows).length!==1||humanRecipeShelf(rows)[0].title!=='Lista')throw Error('drafts exposed');
if(humanRecipeShelf(rows,true).length!==1||humanRecipeShelf(rows,true)[0].title!=='Borrador')throw Error('drafts deleted');
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)


def test_saved_recipes_sessions_and_weeks_are_not_silently_evicted(tmp_path, monkeypatch):
    store = HomeFoodStore(tmp_path / "home.json")
    recipe = {"title": "Receta QA", "servings": 1, "ingredients": [{"name": "Agua", "quantity": 1, "unit": "taza"}], "steps": ["Prueba de almacenamiento"]}
    first = store.save_recipe("qa", recipe)
    first_session = store.start_cooking_session("qa", first["id"])
    first_week = store.save_weekly_plan("qa", {"days": []})
    for index in range(101):
        store.save_recipe("qa", {**recipe, "title": f"QA {index}"})
        store.start_cooking_session("qa", first["id"])
    for _ in range(21):
        store.save_weekly_plan("qa", {"days": []})
    snapshot = store.snapshot("qa")
    assert snapshot["recipes"][0]["id"] == first["id"]
    assert snapshot["cooking_sessions"][0]["id"] == first_session["id"]
    assert snapshot["weekly_plans"][0]["id"] == first_week["id"]
    monkeypatch.setitem(HOME_COLLECTION_LIMITS, "recipes", 102)
    with pytest.raises(ValueError, match="No se borró"):
        store.save_recipe("qa", recipe)
    assert store.snapshot("qa") == snapshot


def test_uncertain_gps_does_not_assert_a_place_or_leaving_work(tmp_path):
    store = HomeFamilyStore(tmp_path / "family.json")
    store.save_place("qa", name="Trabajo", kind="WORK", latitude=28.5, longitude=-81.3, radius_m=200)
    store.update_location("qa", "person", latitude=28.5, longitude=-81.3, accuracy_m=10, consent=True)
    result = store.update_location("qa", "person", latitude=28.503, longitude=-81.3, accuracy_m=500, consent=True, shopping_pending=3)
    assert result["alert"] is None and not result["location"]["place_id"]
    snapshot = store.snapshot("qa", [{"id": "person"}], "person")
    assert snapshot["members"][0]["status"] == "Ubicación aproximada"


def test_older_position_cannot_replace_newer_location(tmp_path):
    store = HomeFamilyStore(tmp_path / "family.json")
    now = datetime.now(timezone.utc)
    first = store.update_location("qa", "person", latitude=28, longitude=-81, accuracy_m=10, recorded_at=now.isoformat(), consent=True)
    old = store.update_location("qa", "person", latitude=20, longitude=-70, accuracy_m=10, recorded_at=(now-timedelta(minutes=2)).isoformat(), consent=True)
    assert old["ignored"] == "OLDER_POSITION" and old["location"] == first["location"]
    assert len(store.history("qa", "person")) == 1


@pytest.mark.parametrize("overrides", [{"latitude": 100}, {"longitude": -190}, {"accuracy_m": -1}, {"accuracy_m": float("nan")}, {"latitude": float("inf")}, {"recorded_at": "bad"}, {"recorded_at": "2026-01-01"}])
def test_invalid_gps_is_rejected(overrides, tmp_path):
    with pytest.raises(ValueError):
        HomeFamilyStore(tmp_path / "family.json").update_location("qa", "person", **{"latitude": 28, "longitude": -81, "accuracy_m": 10, "consent": True, **overrides})


def test_weather_codes_and_real_radar_frames():
    source = (ROOT / "assets/roxy_list.js").read_text()
    weather = source[source.index("  function familyWeatherMode()"):source.index("  function renderFamilyWeatherFx()")]
    radar = source[source.index("  function validatedFamilyRadarMetadata("):source.index("  function familyWeatherGlobeCenter()")]
    script = weather + radar + """
let homeWeather={status:'READY',current:{code:null}};
if(familyWeatherMode()!=='')throw Error('null weather');
for(const code of [61,80,81,82]){homeWeather.current.code=code;if(familyWeatherMode()!=='rain')throw Error('rain mapped to snow');}
for(const code of [71,73,75,77,85,86]){homeWeather.current.code=code;if(familyWeatherMode()!=='snow')throw Error('snow');}
const now=1800000000000, latest=Math.floor(now/1000);
const frames=Array.from({length:13},(_,i)=>({time:latest-i*600,path:'/v2/radar/'+(latest-i*600)}));
const valid=validatedFamilyRadarMetadata({host:'https://tilecache.rainviewer.com',radar:{past:frames}},now);
if(valid.frames.length!==13||valid.frames[0].time>=valid.frames[12].time)throw Error('timeline');
const hashed=validatedFamilyRadarMetadata({host:'https://tilecache.rainviewer.com',radar:{past:[null,{time:latest,path:'/v2/radar/f31d06902b68'}]}},now);
if(hashed.frames.length!==1||hashed.frames[0].path!=='/v2/radar/f31d06902b68')throw Error('rejected current opaque API path');
for(const path of ['/v2/radar/../../private','https://untrusted.example/tile','/v2/radar/123?secret=x','/v2/radar/123/other']){
 let rejected=false;try{validatedFamilyRadarMetadata({host:'https://tilecache.rainviewer.com',radar:{past:[{time:latest,path}]}},now)}catch(e){rejected=true}if(!rejected)throw Error('accepted unsafe frame path');
}
for(const bad of [{host:'https://untrusted.example',radar:{past:frames}},{host:'https://tilecache.rainviewer.com',radar:{past:[{time:latest-7200,path:'/v2/radar/'+(latest-7200)}]}}]){
 let rejected=false;try{validatedFamilyRadarMetadata(bad,now)}catch(e){rejected=true}if(!rejected)throw Error('accepted stale/unknown radar');
}
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
