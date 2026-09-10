"""Bounded source-backed garden entries; no external API or real household."""
import base64

import pytest

from roxy_os.home_plants import HomePlantStore, PLANT_CATALOG, public_plant


PHOTO = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xffsynthetic-garden\xff\xd9").decode("ascii")


@pytest.mark.parametrize("key,name", [("mango", "Mangifera indica"), ("rosemary", "Salvia rosmarinus")])
def test_new_edibles_can_be_selected_and_persist_their_own_profile(tmp_path, key, name):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("household", "member", {"species_key": key, "photo_data_url": PHOTO, "growing_medium": "soil", "drainage": True, "light_exposure": "direct_morning"})
    result = store.snapshot("household", "member")["plants"][0]
    assert plant["identification"]["status"] == "CONFIRMED"
    assert result["scientific_name"] == name
    assert result["soil_rule"] == PLANT_CATALOG[key]["soil_rule"]
    assert len(result["sources"]) == 3
    assert all(row["url"].startswith("https://") for row in result["sources"])
    assert result["source_reviewed_on"] == "2026-09-10"
    assert "propuestas de Roxy" in result["reminder_scope"]
    assert result["space"] and result["container_notes"]


def test_mango_does_not_receive_tropical_houseplant_light_or_rotation_advice(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("household", "member", {"species_key": "mango", "photo_data_url": PHOTO, "growing_medium": "soil", "light_exposure": "low"})
    result = public_plant(plant, "member")
    assert "Pleno sol" in result["light"]
    assert any("pleno sol" in row for row in result["condition_concerns"])
    assert "24–30 °C" in result["temperature"]
    assert result["pet_safe"] is None
    assert "No se ha verificado" in result["toxicity"]
    assert any("edad" in row for row in result["setup_questions"])
    assert any("espacio del árbol" in row["title"] for row in result["care_tasks"])
    assert not any("Rotar la maceta" in row["title"] for row in result["care_tasks"])
    assert all("houseplants" not in row["url"] for row in result["sources"])


def test_confirmed_mango_source_guidance_remains_gated_by_unknown_or_water_medium(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("household", "member", {"species_key": "mango", "photo_data_url": PHOTO})
    unknown = public_plant(plant, "member")
    assert "confirma si está en tierra" in unknown["soil_rule"]
    assert unknown["product_queries"] == []
    changed = store.update("household", plant["id"], {"growing_medium": "water"})
    water = public_plant(changed, "member")
    assert "Confirma una guía de cultivo en agua" in water["soil_rule"]
    assert water["product_queries"] == []
    assert water["photo_url"] == unknown["photo_url"]


def test_rosemary_pet_statement_is_source_specific_not_universal():
    row = PLANT_CATALOG["rosemary"]
    assert "perros, gatos y caballos" in row["toxicity"]
    assert "otras mascotas" in row["toxicity"]
    assert "aceites esenciales" in row["toxicity"]
    assert "No se asigna una dosis" in row["fertilizer"]


def test_species_sources_are_not_shared_mutable_state(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("household", "member", {"species_key": "mango", "photo_data_url": PHOTO, "growing_medium": "soil"})
    first = public_plant(plant, "member")
    first["sources"][0]["label"] = "Changed in client"
    assert public_plant(plant, "member")["sources"][0]["label"].startswith("UF/IFAS")
