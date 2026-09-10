"""Text-only garden reviews use synthetic plants; never public household data."""
import base64

import pytest

from roxy_os.home_plants import HomePlantStore


PHOTO = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xffsynthetic-plant\xff\xd9").decode("ascii")


def fixture(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("household", "member", {"species_key": "pothos", "photo_data_url": PHOTO, "growing_medium": "soil"})
    return store, plant


def test_written_review_requires_no_photo_and_preserves_original(tmp_path):
    store, plant = fixture(tmp_path)
    original = store.plant("household", plant["id"])
    entry = store.add_journal("household", plant["id"], "member", "La tierra sigue húmeda. No regué.")
    updated = store.plant("household", plant["id"])
    public = store.snapshot("household", "member")["plants"][0]
    assert entry["notes"] == "La tierra sigue húmeda. No regué."
    assert entry["photo_path"] == ""
    assert "photo_url" not in public["journal"][0]
    assert updated["photo_path"] == original["photo_path"]
    assert updated["care_tasks"] == original["care_tasks"], "A note is not an explicit watered/task-completed action"
    assert store.snapshot("other-household", "other")["plants"] == []


def test_empty_journal_entry_is_rejected_without_mutation(tmp_path):
    store, plant = fixture(tmp_path)
    with pytest.raises(ValueError, match="observaste"):
        store.add_journal("household", plant["id"], "member", "   ")
    assert store.plant("household", plant["id"])["journal"] == []


def test_supplied_invalid_image_is_not_ignored_as_text_only(tmp_path):
    store, plant = fixture(tmp_path)
    with pytest.raises(ValueError):
        store.add_journal("household", plant["id"], "member", "Nota válida", "data:image/svg+xml;base64,AAAA")
    assert store.plant("household", plant["id"])["journal"] == []


def test_archived_plant_cannot_receive_review(tmp_path):
    store, plant = fixture(tmp_path)
    store.delete("household", plant["id"])
    with pytest.raises(KeyError):
        store.add_journal("household", plant["id"], "member", "No guardar aquí", PHOTO)
    assert not (tmp_path / "images" / "household" / plant["id"] / "journal").exists()


def test_foreign_household_cannot_write_image_before_authorization(tmp_path):
    store, plant = fixture(tmp_path)
    with pytest.raises(KeyError):
        store.add_journal("other-household", plant["id"], "other", "No autorizado", PHOTO)
    assert not (tmp_path / "images" / "other-household").exists()
    assert store.plant("household", plant["id"])["journal"] == []


@pytest.mark.parametrize("result", ["CHECKED", "WATERED"])
def test_explicit_result_persists_without_task_and_is_public_in_private_snapshot(tmp_path, result):
    store, plant = fixture(tmp_path)
    tasks_before = store.plant("household", plant["id"])["care_tasks"]
    entry = store.add_journal("household", plant["id"], "member", "Observación confirmada por la persona.", result=result)
    assert entry["result"] == result
    assert HomePlantStore(store.path, store.image_root).snapshot("household", "member")["plants"][0]["journal"][0]["result"] == result
    assert store.plant("household", plant["id"])["care_tasks"] == tasks_before


@pytest.mark.parametrize("notes", ["No regué.", "Ayer regué.", "I watered yesterday."])
def test_legacy_notes_never_infer_a_result(tmp_path, notes):
    store, plant = fixture(tmp_path)
    entry = store.add_journal("household", plant["id"], "member", notes)
    assert "result" not in entry
    assert "result" not in store.snapshot("household", "member")["plants"][0]["journal"][0]


@pytest.mark.parametrize("result", ["REVIEWED", "", "watered", "CHECKED;WATERED", True, 1, [], {}])
def test_result_rejects_unknown_values_without_writing_media_or_journal(tmp_path, result):
    store, plant = fixture(tmp_path)
    with pytest.raises(ValueError, match="elegida explícitamente"):
        store.add_journal("household", plant["id"], "member", "Con foto", PHOTO, result=result)
    assert store.plant("household", plant["id"])["journal"] == []
    assert not (tmp_path / "images" / "household" / plant["id"] / "journal").exists()


def test_result_and_review_photo_survive_growing_medium_edit_without_replacing_original(tmp_path):
    store, plant = fixture(tmp_path)
    original = store.plant("household", plant["id"])["photo_path"]
    entry = store.add_journal("household", plant["id"], "member", "Solo revisé las hojas; no regué.", PHOTO, result="CHECKED")
    updated = store.update("household", plant["id"], {"growing_medium": "water", "drainage": None})
    assert updated["growing_medium"] == "water" and updated["drainage"] is None
    assert updated["photo_path"] == original
    assert updated["journal"][0] == entry
    result = store.snapshot("household", "member")["plants"][0]
    assert result["journal"][0]["result"] == "CHECKED"
    assert result["journal"][0]["photo_url"].endswith(f"/journal/{entry['id']}/image")
    assert result["photo_url"].endswith(f"/{plant['id']}/image")
