"""Regressions found through the visible, whole-Home audit."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from html.parser import HTMLParser
import json
import re
from pathlib import Path
import subprocess

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from roxy_os.home_family import HomeFamilyStore
from roxy_os.home_recipe_editorial import recipe_quality_issues

ROOT = Path(__file__).resolve().parents[1]


def test_focus_version_check_matches_html_release_not_worker_cache():
    html = (ROOT / "assets/roxy_list.html").read_text()
    js = (ROOT / "assets/roxy_list.js").read_text()
    html_version = re.search(r'name="roxy-home-version" content="([^"]+)"', html).group(1)
    js_version = re.search(r"const APP_VERSION = '([^']+)'", js).group(1)
    assert html_version == js_version, "Focusing the app must not reload and discard the active form"


def test_default_number_fields_are_valid_steps():
    class Inputs(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag != "input" or attrs.get("type") != "number" or not attrs.get("value"):
                return
            step = attrs.get("step", "1")
            if step == "any":
                return
            value = Decimal(attrs["value"])
            base = Decimal(attrs.get("min", attrs["value"]))
            assert (value - base) % Decimal(step) == 0, attrs["id"]
    Inputs().feed((ROOT / "assets/roxy_list.html").read_text())


def test_photo_rate_limit_does_not_block_household_operations():
    from tools import roxy_home_service as service
    request = Request({"type": "http", "client": ("audit-test", 1234)})
    service._RATE_STATE.clear()
    for _ in range(service.RATE_LIMIT_MAX):
        service._rate_limit(request, bucket="recipe-media")
    with pytest.raises(HTTPException) as caught:
        service._rate_limit(request, bucket="recipe-media")
    assert caught.value.status_code == 429
    assert int(caught.value.headers["Retry-After"]) > 0
    service._rate_limit(request)
    service._RATE_STATE.clear()


def test_family_keeps_private_members_and_labels_stale_positions(tmp_path):
    store = HomeFamilyStore(tmp_path / "family.json")
    members = [{"id": "owner", "display_name": "Owner"}, {"id": "partner", "display_name": "Partner"}]
    old = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    store.update_location("house", "partner", latitude=28, longitude=-81, accuracy_m=10, recorded_at=old, consent=True)
    snapshot = store.snapshot("house", members, "owner")
    assert len(snapshot["members"]) == 2
    owner, partner = snapshot["members"]
    assert owner["location"] is None
    assert owner["presence_status"] == "PRIVATE"
    assert partner["presence_status"] == "STALE"
    assert partner["status"] == "Última ubicación"
    assert "ahora" not in partner["status"]


def test_voice_payment_error_is_actionable_without_exposing_details():
    source = (ROOT / "assets/roxy_list.js").read_text()
    function = source[source.index("  function roxyVoiceError("):source.index("  async function sendRoxyText(")]
    script = function + "\nconsole.log(JSON.stringify(roxyVoiceError({name:'SessionConnectionError', message:'[payment_issue] secret-account'}, 'start')));"
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    text = json.loads(result.stdout)
    assert "pago pendiente" in text
    assert "escribirle" in text
    assert "secret-account" not in text


def test_catalog_inventory_has_separate_care_and_recipe_counts():
    from tools.roxy_home_catalog_audit import audit_catalog
    result = audit_catalog()
    assert result["total"] == 668
    assert result["modules"] == {"human_recipes": 517, "pet_care": 94, "pet_recipes": 57}
    assert result["editorial_statuses"]["needs_canonical_review"] == 458
    cesar = next(row for row in result["recipes"] if row["title"] == "Aderezo César")
    assert any("propio ingrediente" in issue for issue in cesar["checks"])


def test_ui_honors_hidden_and_preserves_private_nexo_members():
    css = (ROOT / "assets/roxy_list.css").read_text()
    script = (ROOT / "assets/roxy_list.js").read_text()
    assert "[hidden] { display: none !important; }" in css
    select = script[script.index("  function familySelectedMember()"):script.index("  function familyNextCalendarEvent()")]
    assert "filter" not in select
    assert "Frecuencia guardada" in script
    assert "Pendiente de revisión · no lista para cocinar" in script


def test_failed_editorial_review_never_returns_the_defective_offline_recipe(monkeypatch):
    from tools import roxy_home_service as service
    class AI:
        def curate_recipe(self, *args):
            raise ValueError("unavailable")
    class Library:
        def find(self, *args, **kwargs):
            return None
    monkeypatch.setattr(service, "_home_ai", lambda: AI())
    monkeypatch.setattr(service, "_recipe_library_store", lambda: Library())
    with pytest.raises(ValueError, match="unavailable"):
        service._recipe_with_resilience("Aderezo César", {}, deep=False)


def test_saved_draft_cannot_start_cooking_or_change_shopping(tmp_path):
    from roxy_os.home_food import HomeFoodStore, RecipeReviewRequired
    from roxy_os.shopping_list import ShoppingListStore
    store = HomeFoodStore(tmp_path / "food.json")
    shopping = ShoppingListStore(tmp_path / "shopping.json")
    recipe = store.save_recipe("qa", {"title": "Borrador QA", "editorial_status": "needs_canonical_review", "servings": 1, "ingredients": [{"name": "Borrador QA", "quantity": 1, "unit": "unidad"}], "steps": ["Revisar."]})
    before = store.snapshot("qa")
    with pytest.raises(RecipeReviewRequired):
        store.start_cooking_session("qa", recipe["id"])
    with pytest.raises(RecipeReviewRequired):
        store.commit_recipe_to_shopping("qa", recipe["id"], shopping, confirmed=True)
    assert store.snapshot("qa") == before


def test_editorial_draft_does_not_spend_image_generation(monkeypatch):
    from tools import roxy_home_service as service
    monkeypatch.setattr(service, "_recipe_photo_queue", lambda: pytest.fail("Draft must not schedule artwork"))
    assert service._schedule_recipe_photo({"editorial_status": "needs_canonical_review"}) == "REVIEW_REQUIRED"


def test_sourced_recipe_is_not_downgraded_to_catalog_template():
    from roxy_os.home_food import HomeFoodStore
    recipe = {"title": "Aderezo César", "editorial_status": "verified_with_sources", "steps": ["Mezcla los ingredientes medidos."], "ingredients": [{"name": "Limón", "quantity": 1, "unit": "unidad"}]}
    before = json.loads(json.dumps(recipe))
    HomeFoodStore._upgrade_installed_recipe(recipe)
    assert recipe == before


def test_photo_coverage_does_not_claim_generation_with_empty_queue(monkeypatch):
    from tools import roxy_home_service as service
    class Photos:
        def resolve(self, title):
            return None
    class Queue:
        def public_status(self):
            return {"pending": 0}
        def failure_summary(self):
            return {}
    monkeypatch.setattr(service, "_all_recipe_photo_rows", lambda: [{"title": "QA"}])
    monkeypatch.setattr(service, "_recipe_photo_store", lambda: Photos())
    monkeypatch.setattr(service, "_recipe_photo_queue", lambda: Queue())
    assert service.recipe_photo_coverage()["status"] == "INCOMPLETE"


def test_known_mismatched_photo_is_quarantined_without_deleting(tmp_path):
    import base64
    from roxy_os.home_recipe_photos import RecipePhotoStore
    store = RecipePhotoStore(tmp_path, built_in_root=tmp_path / "built-in")
    path = store.save_generated("Aderezo César", base64.b64encode(b"\x89PNG\r\n\x1a\nillustration").decode(), approved=True)
    assert store.resolve("Aderezo César") is None
    assert path.exists()


def test_client_does_not_reuse_mismatched_cached_photo():
    source = (ROOT / "assets/roxy_list.js").read_text()
    function = source[source.index("  const recipeImage ="):source.index("  const waitForRecipeImage =")]
    result = subprocess.run(["node", "-e", function + "\nconsole.log(JSON.stringify(recipeImage({title:'Aderezo César'})));"], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == ""


def test_partial_load_never_overwrites_garden_or_design_cache_with_empty():
    source = (ROOT / "assets/roxy_list.js").read_text()
    assert "if(plantsData)await dbSet" in source
    assert "if(designData)await dbSet" in source
    assert "if (cachedPlants) homePlants = cachedPlants" in source


def test_cancelled_voice_permission_never_opens_a_late_session():
    source = (ROOT / "assets/roxy_list.js").read_text()
    functions = source[source.index("  async function startRoxyVoice()"):source.index("  function renderProductLookup(")]
    harness = r"""
let resolvePermission, stopped=0, configCalls=0;
let roxyVoiceConversation=null, roxyVoiceStarting=false, roxyVoiceAttempt=0, roxyVoicePermissionStream=null, roxyLastAgentMessage='',roxyLastAgentMessageAt=0;
const controls={}; const $=id=>controls[id]||(controls[id]={});
const openRoxyVoice=()=>{}, roxyVoiceStatus=()=>{}, roxyVoiceError=()=>'';
const navigator={mediaDevices:{getUserMedia:()=>new Promise(resolve=>{resolvePermission=resolve})}};
const api=async()=>{configCalls++;throw Error('Should not be reached')};
const stopRoxyPermissionStream=()=>{if(roxyVoicePermissionStream)roxyVoicePermissionStream.getTracks().forEach(track=>track.stop());roxyVoicePermissionStream=null};
const user='qa';
"""
    harness += functions + r"""
(async()=>{const pending=startRoxyVoice();await endRoxyVoice();resolvePermission({getTracks:()=>[{stop:()=>stopped++}]});await pending;console.log(JSON.stringify({stopped,configCalls,starting:roxyVoiceStarting}));})();
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {"stopped": 1, "configCalls": 0, "starting": False}


def test_voice_cleanup_does_not_override_a_new_session():
    source = (ROOT / "assets/roxy_list.js").read_text()
    function = source[source.index("  async function endRoxyVoice()"):source.index("  function renderProductLookup(")]
    harness = r"""
let resolveEnd,roxyVoiceAttempt=0,roxyVoiceStarting=false,status='old';
let roxyVoiceConversation={endSession:()=>new Promise(resolve=>{resolveEnd=resolve})};
const controls={};const $=id=>controls[id]||(controls[id]={});
const stopRoxyPermissionStream=()=>{},roxyVoiceStatus=text=>{status=text};
"""
    harness += function + r"""
(async()=>{const pending=endRoxyVoice();roxyVoiceAttempt++;roxyVoiceStarting=true;status='new';resolveEnd();await pending;console.log(JSON.stringify({status,starting:roxyVoiceStarting}));})();
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {"status": "new", "starting": True}
