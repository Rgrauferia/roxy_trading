from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json

import pytest

from roxy_os.home_accounts import HomeAccountStorageError, HomeAccountStore
from roxy_os.home_recipe_profile import (
    RecipeProfileConflictError, RecipeProfileValidationError, normalize_recipe_profile,
    recipe_profile_options,
)


def completed_profile(**changes):
    return {
        "schema_version": 1, "completed": True, "consent": True,
        "language": "es", "country_of_origin": "", "cuisine_mode": "mixed",
        "cuisines": [], "favorite_foods": ["rice", "legumes"],
        "diet": "omnivore", "allergy_status": "undisclosed", "allergies": [],
        "other_allergies": "", "dislikes": [], "max_minutes": 30,
        "skill": "beginner", **changes,
    }


@pytest.fixture
def account(tmp_path, monkeypatch):
    # Password strength has its own suite; avoid repeated expensive PBKDF2 here.
    monkeypatch.setattr("roxy_os.home_accounts.PASSWORD_ITERATIONS", 100_000)
    path = tmp_path / "accounts.json"
    store = HomeAccountStore(path)
    owner = store.bootstrap("recipe-test", household_name="Casa", username="owner",
                            display_name="Owner", password="test-password")
    partner = store.add_member(owner["id"], username="partner", display_name="Partner", password="test-password")
    return store, owner, partner


def test_options_are_independent_and_canonical():
    options = recipe_profile_options()
    options["cuisines"][0]["value"] = "changed"
    assert recipe_profile_options()["cuisines"][0]["value"] == "mexican"
    assert {row["value"] for row in options["allergy_statuses"]} == {"none", "listed", "undisclosed"}


def test_completed_profile_can_omit_private_answers_without_inference():
    result = normalize_recipe_profile(completed_profile(
        country_of_origin="  Perú  ", diet="undisclosed", skill="undisclosed",
        max_minutes=None, favorite_foods=[],
    ))
    assert result["country_of_origin"] == "Perú"
    assert result["cuisines"] == []
    assert result["cuisine_mode"] == "mixed"
    assert result["allergy_status"] == "undisclosed"


def test_explicit_choices_lists_and_custom_allergy_are_preserved():
    source = completed_profile(
        cuisine_mode="selected", cuisines=["peruvian", "italian", "peruvian"],
        allergy_status="listed", allergies=["milk", "other"], other_allergies="  Kiwi  ",
        dislikes=["  cilantro  ", "CILANTRO", "Ajo"],
    )
    result = normalize_recipe_profile(source)
    assert result["cuisines"] == ["peruvian", "italian"]
    assert result["other_allergies"] == "Kiwi"
    assert result["dislikes"] == ["cilantro", "Ajo"]
    result["cuisines"].append("spanish")
    assert source["cuisines"] == ["peruvian", "italian", "peruvian"]


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("schema_version", "1"), ("schema_version", 2),
    ("completed", "true"), ("completed", 1), ("consent", False), ("consent", 1),
    ("language", None), ("language", "fr"), ("country_of_origin", 12),
    ("country_of_origin", "x" * 65), ("country_of_origin", "Peru\x00"),
    ("cuisine_mode", None), ("cuisine_mode", "automatic"),
    ("cuisines", "peruvian"), ("cuisines", ["unknown"]), ("cuisines", [[]]),
    ("favorite_foods", ["unknown"]), ("diet", None), ("diet", "keto"),
    ("allergy_status", None), ("allergy_status", "unknown"),
    ("allergies", "milk"), ("allergies", ["gluten_free"]),
    ("dislikes", "cilantro"), ("dislikes", [None]), ("dislikes", [""]),
    ("dislikes", ["x" * 61]), ("dislikes", ["x"] * 21),
    ("max_minutes", True), ("max_minutes", "30"), ("max_minutes", 5.5),
    ("max_minutes", 0), ("max_minutes", 241), ("skill", None), ("skill", "expert"),
])
def test_malformed_fields_are_rejected_without_coercion(field, value):
    with pytest.raises(RecipeProfileValidationError):
        normalize_recipe_profile(completed_profile(**{field: value}))


@pytest.mark.parametrize("changes", [
    {"member_id": "another-member"},
    {"cuisine_mode": "origin", "country_of_origin": ""},
    {"cuisine_mode": "selected", "cuisines": []},
    {"allergy_status": "listed", "allergies": []},
    {"allergy_status": "none", "allergies": ["milk"]},
    {"allergy_status": "undisclosed", "allergies": ["milk"]},
    {"allergy_status": "listed", "allergies": ["other"], "other_allergies": ""},
    {"allergy_status": "listed", "allergies": ["milk"], "other_allergies": "kiwi"},
])
def test_conflicting_or_incomplete_choices_cannot_complete(changes):
    with pytest.raises(RecipeProfileValidationError):
        normalize_recipe_profile(completed_profile(**changes))


def test_draft_is_explicit_and_never_assumes_no_allergies():
    result = normalize_recipe_profile({"schema_version": 1, "completed": False, "consent": True})
    assert result["completed"] is False
    assert result["allergy_status"] is None
    assert result["language"] is None
    assert result["allergies"] == []


def test_new_members_require_profile_but_read_does_not_write(account):
    store, owner, partner = account
    before = store.path.read_bytes()
    state = store.get_recipe_profile(owner["id"])
    assert state["profile"] is None and state["revision"] == 0 and state["required"] is True
    assert state["member_id"] == owner["id"]
    assert owner["recipe_onboarding_required"] is True
    assert partner["recipe_onboarding_required"] is True
    assert store.path.read_bytes() == before


def test_legacy_members_are_not_forced_into_onboarding(account):
    store, owner, _ = account
    raw = json.loads(store.path.read_text())
    del raw["members"][owner["id"]]["recipe_onboarding_required"]
    store.path.write_text(json.dumps(raw))
    assert store.member(owner["id"])["recipe_onboarding_required"] is False
    assert store.get_recipe_profile(owner["id"])["required"] is False


def test_trial_registration_requires_new_member_profile(tmp_path, monkeypatch):
    monkeypatch.setattr("roxy_os.home_accounts.PASSWORD_ITERATIONS", 100_000)
    store = HomeAccountStore(tmp_path / "accounts.json")
    member = store.register_trial(username="trial", display_name="Trial", password="test-password", admission_hash="local-test")
    assert member["recipe_onboarding_required"] is True
    assert store.get_recipe_profile(member["id"])["required"] is True


def test_profile_persists_privately_with_timestamps_without_changing_household_or_other_member(account):
    store, owner, partner = account
    before = json.loads(store.path.read_text())
    before["members"][owner["id"]]["future_personal_field"] = {"kept": True}
    store.path.write_text(json.dumps(before))
    saved = store.update_recipe_profile(owner["id"], profile=completed_profile(), expected_revision=0)
    assert saved["revision"] == 1 and saved["required"] is False
    after = json.loads(store.path.read_text())
    assert before["households"] == after["households"]
    assert before["members"][partner["id"]] == after["members"][partner["id"]]
    assert after["members"][owner["id"]]["future_personal_field"] == {"kept": True}
    for key in before["members"][owner["id"]]:
        assert after["members"][owner["id"]][key] == before["members"][owner["id"]][key]
    for suffix in ("created_at", "updated_at", "completed_at", "consented_at"):
        assert after["members"][owner["id"]]["recipe_profile_" + suffix]
    reloaded = HomeAccountStore(store.path).get_recipe_profile(owner["id"])
    assert reloaded == saved
    assert store.get_recipe_profile(partner["id"])["profile"] is None
    assert (store.path.stat().st_mode & 0o777) == 0o600


def test_public_member_views_never_leak_recipe_preferences(account):
    store, owner, partner = account
    store.update_recipe_profile(owner["id"], profile=completed_profile(
        allergy_status="listed", allergies=["other"], other_allergies="private-kiwi",
    ), expected_revision=0)
    responses = [store.member(owner["id"]), store.members(partner["id"]),
                 store.authenticate("owner", "test-password")]
    serialized = json.dumps(responses)
    assert "private-kiwi" not in serialized
    assert "recipe_profile" not in serialized
    assert "allergy_status" not in serialized
    assert store.member(owner["id"])["recipe_onboarding_required"] is False


def test_settings_update_preserves_recipe_profile(account):
    store, owner, _ = account
    saved = store.update_recipe_profile(owner["id"], profile=completed_profile(), expected_revision=0)
    store.update_personalization(owner["id"], display_name="New name", preferences={"theme": "olive"})
    assert store.get_recipe_profile(owner["id"]) == saved


def test_save_is_full_replacement_and_previous_completion_remains_dated(account):
    store, owner, _ = account
    store.update_recipe_profile(owner["id"], profile=completed_profile(dislikes=["cilantro"]), expected_revision=0)
    first = json.loads(store.path.read_text())["members"][owner["id"]]
    changed = store.update_recipe_profile(owner["id"], profile=completed_profile(dislikes=[], max_minutes=None), expected_revision=1)
    second = json.loads(store.path.read_text())["members"][owner["id"]]
    assert changed["revision"] == 2
    assert changed["profile"]["dislikes"] == []
    assert changed["profile"]["max_minutes"] is None
    assert second["recipe_profile_completed_at"] == first["recipe_profile_completed_at"]
    assert second["recipe_profile_created_at"] == first["recipe_profile_created_at"]
    assert second["recipe_profile_updated_at"] >= first["recipe_profile_updated_at"]


@pytest.mark.parametrize("revision", [True, -1, "0", None])
def test_invalid_revision_rejected_without_changes(account, revision):
    store, owner, _ = account
    before = store.path.read_bytes()
    with pytest.raises(RecipeProfileValidationError):
        store.update_recipe_profile(owner["id"], profile=completed_profile(), expected_revision=revision)
    assert store.path.read_bytes() == before


def test_stale_revision_conflict_preserves_latest_profile(account):
    store, owner, _ = account
    store.update_recipe_profile(owner["id"], profile=completed_profile(), expected_revision=0)
    before = store.path.read_bytes()
    with pytest.raises(RecipeProfileConflictError):
        store.update_recipe_profile(owner["id"], profile=completed_profile(language="en"), expected_revision=0)
    assert store.path.read_bytes() == before


def test_concurrent_store_instances_have_one_revision_winner(account):
    store, owner, _ = account
    def save(language):
        try:
            return HomeAccountStore(store.path).update_recipe_profile(
                owner["id"], profile=completed_profile(language=language), expected_revision=0,
            )["profile"]["language"]
        except RecipeProfileConflictError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(save, ["es", "en"]))
    assert outcomes.count("conflict") == 1
    assert store.get_recipe_profile(owner["id"])["revision"] == 1


@pytest.mark.parametrize("malformation", ["inactive", "missing_household", "unknown_member"])
def test_private_profile_requires_active_membership(account, malformation):
    store, owner, _ = account
    raw = json.loads(store.path.read_text())
    member_id = owner["id"]
    if malformation == "inactive":
        raw["members"][member_id]["active"] = False
    elif malformation == "missing_household":
        del raw["households"][owner["household_id"]]
    else:
        member_id = "does-not-exist"
    store.path.write_text(json.dumps(raw))
    before = store.path.read_bytes()
    with pytest.raises(PermissionError):
        store.get_recipe_profile(member_id)
    with pytest.raises(PermissionError):
        store.update_recipe_profile(member_id, profile=completed_profile(), expected_revision=0)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("mutation", [
    {"recipe_profile_revision": True}, {"recipe_profile_revision": -1},
    {"recipe_profile_revision": 2}, {"recipe_profile": "broken"},
    {"recipe_profile": completed_profile(), "recipe_profile_revision": 0},
    {"recipe_profile": completed_profile(consent=False), "recipe_profile_revision": 1},
])
def test_malformed_saved_profile_fails_closed_and_preserves_bytes(account, mutation):
    store, owner, _ = account
    raw = json.loads(store.path.read_text())
    raw["members"][owner["id"]].update(deepcopy(mutation))
    store.path.write_text(json.dumps(raw))
    before = store.path.read_bytes()
    with pytest.raises(HomeAccountStorageError):
        store.get_recipe_profile(owner["id"])
    with pytest.raises(HomeAccountStorageError):
        store.update_recipe_profile(owner["id"], profile=completed_profile(), expected_revision=0)
    assert store.path.read_bytes() == before


def test_rejected_save_and_storage_error_preserve_last_durable_profile(account, monkeypatch):
    store, owner, _ = account
    store.update_recipe_profile(owner["id"], profile=completed_profile(), expected_revision=0)
    before = store.path.read_bytes()
    with pytest.raises(RecipeProfileValidationError):
        store.update_recipe_profile(owner["id"], profile=completed_profile(allergy_status=None), expected_revision=1)
    assert store.path.read_bytes() == before
    def fail_write(_):
        raise OSError("synthetic disk write failure")
    monkeypatch.setattr(store, "_write_unlocked", fail_write)
    with pytest.raises(OSError):
        store.update_recipe_profile(owner["id"], profile=completed_profile(language="en"), expected_revision=1)
    assert store.path.read_bytes() == before
