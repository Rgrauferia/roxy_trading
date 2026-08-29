import json
from pathlib import Path

from fastapi.testclient import TestClient

from roxy_os.shopping_list import ShoppingListStore, normalize_shopping_name


def test_roxy_home_list_pwa_shell_is_installable_and_offline_capable():
    from tools import roxy_home_service

    client = TestClient(roxy_home_service.app)
    page = client.get("/lista")
    manifest = client.get("/lista-manifest.json")
    worker = client.get("/lista-sw.js")
    script = client.get("/assets/roxy_list.js")
    style = client.get("/assets/roxy_list.css")
    home_avatar = client.get("/assets/roxy_home_avatar.jpg")
    pet_pads = client.get("/assets/roxy_home/products/pet-training-pads.png")
    scent_beads = client.get("/assets/roxy_home/products/laundry-scent-beads.png")
    toothpaste = client.get("/assets/roxy_home/products/toothpaste.png")

    assert page.status_code == 200
    assert 'href="/lista-manifest.json"' in page.text
    assert 'name="roxy-home-version" content="95"' in page.text
    assert 'href="/assets/roxy_list.css?v=76"' in page.text
    assert 'src="/assets/roxy_list.js?v=95"' in page.text
    assert '/assets/roxy_list.css?v=76' in worker.text
    assert '/assets/roxy_list.js?v=95' in worker.text
    assert 'id="homeWelcome" class="welcome today-welcome" aria-labelledby="pageTitle" hidden' in page.text
    assert '/assets/roxy_home_avatar.jpg' in page.text
    assert '/assets/roxy_home_avatar.jpg' in worker.text
    assert '/assets/roxy_avatar_icon.jpg' in worker.text
    assert '/assets/roxy_home/avatars/monogram.svg' in worker.text
    assert '/assets/roxy_home/products/pet-training-pads.png' in worker.text
    assert '/assets/roxy_home/products/laundry-scent-beads.png' in worker.text
    assert '/assets/roxy_home/products/toothpaste.png' in worker.text
    assert pet_pads.status_code == 200 and pet_pads.content.startswith(b"\x89PNG")
    assert scent_beads.status_code == 200 and scent_beads.content.startswith(b"\x89PNG")
    assert toothpaste.status_code == 200 and toothpaste.content.startswith(b"\x89PNG")
    assert "COPY assets/roxy_home/avatars ./assets/roxy_home/avatars" in Path("Dockerfile.roxy-home").read_text(encoding="utf-8")
    assert manifest.json()["icons"][0]["src"] == "/assets/roxy_home_avatar.jpg"
    assert home_avatar.status_code == 200
    assert home_avatar.headers["content-type"] == "image/jpeg"
    assert home_avatar.content.startswith(b"\xff\xd8\xff")
    assert 'id="designPanel"' in page.text
    assert 'class="renueva-entry"' not in page.text
    assert 'id="openDesignFromToday"' not in page.text
    assert "openDesignFromToday" not in script.text
    nav = page.text[page.text.index('<nav class="bottom-nav"'):]
    assert nav.index('data-tab-link="recipes"') < nav.index('data-tab-link="design"') < nav.index('data-tab-link="calendar"')
    assert 'id="designProjectForm"' in page.text
    assert '/v1/home-design/' in script.text
    assert 'Comparar muebles reales' in script.text
    assert "const APP_VERSION = '95'" in script.text
    assert 'data-close-dialog="pairDialog"' in page.text
    assert "recetas listas para guardar, adaptar y cocinar paso a paso" in script.text
    assert "provider.affiliate_connected?'afiliado':'catálogo oficial'" in script.text
    assert "la foto, medidas, disponibilidad y precio real" in script.text
    assert 'Analizar y rediseñar' in script.text
    assert 'Pídele un cambio a Roxy' in script.text
    assert 'Desliza para comparar la habitación actual y el rediseño' in script.text
    assert 'Guardar medidas' in script.text
    assert '/measurements' in script.text
    assert "economy|balanced|complete" in Path("tools/roxy_home_service.py").read_text(encoding="utf-8")
    assert "CLEANING:'Limpieza'" in script.text
    assert "FOOD:'Alimentos'" in script.text
    assert "HOUSEHOLD:'Hogar y accesorios'" in script.text
    assert "PRODUCE:'Frutas y vegetales'" in script.text
    assert "DAIRY_EGGS:'Lácteos y huevos'" in script.text
    assert "BABY:'Cuidado del bebé'" in script.text
    assert "['Iluminación y electricidad'" in script.text
    assert "shopping-category-group" in script.text
    assert "Automática (recomendada)" in page.text
    assert 'class="meal-plan-limits"' not in page.text
    assert page.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert page.headers["pragma"] == "no-cache"
    assert "event.persisted" in script.text
    assert "registration.update()" in script.text
    assert "refreshStaleApp" in script.text
    assert "img-src 'self' data: blob:" in page.headers["content-security-policy"]
    assert "URL.revokeObjectURL(objectUrl)" in script.text
    assert 'id="todayPanel"' in page.text
    assert 'id="calendarPanel"' in page.text
    assert 'id="calendarGoogleConnect"' in page.text
    assert '/google/connect' in script.text
    assert '/google/sync' in script.text
    assert 'Sincronización automática activa' in script.text
    assert "calendarExportButton').hidden=!existing||googleConnected" in script.text
    assert 'data-tab-link="calendar"' in page.text
    assert '<strong>Calendario</strong>' in page.text
    assert 'id="calendarEventDialog"' in page.text
    assert 'id="calendarConfirmDialog"' in page.text
    assert 'id="upcomingEventCard"' in page.text
    assert 'id="homeDailyBrief"' in page.text
    assert '/v1/home-daily/' in script.text
    assert '/v1/home-calendar/' in script.text
    assert 'Hola, ${person}. ¿Qué hacemos hoy?' in script.text
    assert 'Evento guardado y sincronizado con el calendario de tu teléfono' in script.text
    assert "Notification.requestPermission" in script.text
    assert "data-calendar-view" in page.text
    assert ".calendar-agenda[hidden]" in style.text
    assert 'data-tab-link="today"' in page.text
    assert page.text.index('id="todayPanel"') < page.text.index('id="shoppingPanel"') < page.text.index('id="recipesPanel"')
    assert page.text.index('id="mealPlanStudio"') < page.text.index('id="recipesPanel"')
    assert page.text.index('id="mealPlanStudio"') < page.text.index('id="homeWelcome"')
    assert "{id:'breakfast',title:'Desayunos'" in script.text
    assert "{id:'pasta',title:'Pastas y fideos'" in script.text
    assert "{id:'baked',title:'Horneados'" in script.text
    assert 'aspect-ratio: 16 / 9' in style.text
    assert "media.loop=true" in script.text
    assert "videoSeconds*cycles/audioSeconds" in script.text
    assert "stopSynchronizedStepVideo(true)" in script.text
    assert "visual.hidden=true" in script.text
    assert "root.append(hero,columns,actions)" in script.text
    assert "root.append(hero,videoArea,columns,actions)" not in script.text
    assert 'demostraciones listas' in script.text
    assert "aria-live','polite" in script.text
    assert 'id="cookingVideo"' in page.text
    assert "syncCookingVideo" in script.text
    assert "Roxy está creando las demostraciones" in script.text
    assert "/speech`" in script.text
    assert "Roxy hablando" in script.text
    assert "currentStepVideo" in script.text
    assert "dataset.currentStep='true'" in script.text
    assert "startSynchronizedStepVideo" in script.text
    assert "stopSynchronizedStepVideo" in script.text
    assert "stepTimerSeconds" in script.text
    assert "startAutomaticStepTimer" in script.text
    assert "Roxy inició el temporizador del paso" in script.text
    assert 'id="homeDate"' in page.text
    assert 'id="homeTime"' in page.text
    assert 'id="homeGreeting"' in page.text
    assert 'id="homePerson"' in page.text
    assert 'id="greetingDialog"' in page.text
    assert 'id="greetingSettingsButton"' in page.text
    assert "localStorage.getItem('roxyHomeGreetingName')" in script.text
    assert "localStorage.setItem('roxyHomeGreetingName'" in script.text
    assert "localStorage.removeItem('roxyHomeGreetingName')" in script.text
    assert 'id="loginForm"' in page.text
    assert 'id="accountDialog"' in page.text
    assert 'id="addMemberForm"' in page.text
    assert 'id="personalizationDialog"' in page.text
    assert 'id="personalizationForm"' in page.text
    assert 'Mi Roxy y apariencia' in page.text
    assert 'Roxy clásico' in page.text
    assert 'Olivo natural' in page.text
    assert 'Costa serena' in page.text
    assert 'Terracota' in page.text
    assert '/assets/roxy_home/avatars/monogram.svg' in page.text
    assert "/v1/home-account/login" in script.text
    assert "/v1/home-account/members" in script.text
    assert "/v1/home-account/preferences" in script.text
    assert "data-roxy-avatar" in page.text
    assert "applyAppearance" in script.text
    assert ':root[data-theme="coastal"]' in style.text
    assert ':root[data-background="linen"]' in style.text
    assert "activePersonName" in script.text
    assert 'home-hero-plant.png' in page.text
    assert "Intl.DateTimeFormat('es'" in script.text
    assert 'Roberto' not in page.text
    assert "unsafe-inline" not in page.headers["content-security-policy"]
    assert manifest.json()["start_url"] == "/home"
    assert manifest.json()["scope"] == "/home"
    assert manifest.json()["display"] == "standalone"
    assert worker.headers["service-worker-allowed"] == "/lista"
    assert "indexedDB" in script.text
    assert "navigator.share" in script.text
    assert "startRoxyVoice" in script.text
    assert "Conversation.startSession" in script.text
    assert "connectionType:'websocket'" in script.text
    assert "await navigator.mediaDevices.getUserMedia" in script.text
    assert "permissionStream" not in script.text
    assert "Roxy te está escuchando" in script.text
    assert "handleRoxyShoppingTranscript" not in script.text
    assert "never uses end_call" not in script.text
    assert "@elevenlabs/client@1.8.1" in script.text
    assert "La aplicación actual es Roxy Home" in script.text
    assert "sendCommandToRoxyOS" in script.text
    assert "sendCommandToRoxyOSForVoice" in script.text
    assert "must_speak:true" in script.text
    assert "Lee en voz alta ahora el campo speech completo" in script.text
    assert "No respondas antes de que la herramienta termine" in script.text
    assert "Comprende la intención antes de contestar" in script.text
    assert "No copies listas de datos sin interpretarlas" in script.text
    assert "daily_brief:homeDaily" in script.text
    assert "recoverRoxyVoiceSpeech" in script.text
    assert "sendUserMessage" in script.text
    assert "RESULTADO CONFIRMADO DE ROXY HOME" in script.text
    assert 'id="roxyVoiceLauncher"' in page.text
    assert 'id="roxyPanel"' not in page.text
    assert 'data-tab-link="roxy"' not in page.text
    assert "habitual_products" in script.text
    assert "paper-towels.png" in script.text
    assert "microphone=(self)" in page.headers["permissions-policy"]
    assert "https://*.elevenlabs.io" in page.headers["content-security-policy"]
    assert "worker-src 'self' blob:" in page.headers["content-security-policy"]
    assert "script-src 'self' blob:" in page.headers["content-security-policy"]
    assert "localStorage.setItem('roxyShoppingUser'" in script.text
    assert "localStorage.setItem('apiToken'" not in script.text
    assert 'id="recipeSubmit"' in page.text
    assert 'id="recipeLibrary"' in page.text
    assert 'id="scanRecipeButton"' in page.text
    assert 'id="importRecipeUrlButton"' in page.text
    assert 'id="recipeImportDialog"' in page.text
    assert 'data-recipe-audience="pet"' in page.text
    assert 'data-pet-species="dog"' in page.text
    assert "/recipe-imports" in script.text
    assert "/recipe-imports/commit" in script.text
    assert "/pets`" in script.text
    assert page.text.index('id="recipeLibrary"') < page.text.index('id="recipeForm"')
    assert 'Pídele a Roxy algo diferente' in page.text
    assert 'id="recipeCatalogHint"' in page.text
    assert 'id="cookingDialog"' in page.text
    assert 'data-tab-link="recipes"' in page.text
    assert 'id="pantryForm"' in page.text
    assert 'id="mealPlanForm"' in page.text
    assert 'id="mealPlanShopping"' in page.text
    assert 'name="mealPlanStyle"' in page.text
    assert 'id="mealPlanCookDays"' in page.text
    assert 'id="mealPlanScope"' in page.text
    assert 'id="mealPlanPrepSessions"' in page.text
    assert "/weekly-plans/" in script.text
    assert "updateWeeklyPlanMeal" in script.text
    assert "updateWeeklyPlanDay" in script.text
    assert "mealPlanForm').requestSubmit()" in script.text
    assert "Comeremos sobras" in script.text
    assert "Cambiar ${meal.title}" in script.text
    assert 'id="substitutionForm"' in page.text
    assert "/v1/home-food/" in script.text
    assert "recipeSubmit" in script.text
    assert "shopping-preview" in script.text
    assert "shopping-commit" in script.text
    assert "cooking-sessions" in script.text
    assert "speechSynthesis" in script.text
    assert "/speech`" in script.text
    assert "Roxy hablando" in script.text
    assert "productImages" in script.text
    for asset in ("mandarin.png", "ice-cream.png", "sugar.png", "dulce-de-leche.png", "medicine.png", "eyebrow-gel.png", "scent-sachets.png", "flour.png", "pasta.png", "yogurt.png", "juice.png", "vegetables.png", "beef.png", "fish.png", "shampoo.png", "groceries.png"):
        assert asset in script.text
        assert asset in worker.text
        assert client.get(f"/assets/roxy_home/products/{asset}").status_code == 200
    assert "productLabel" in script.text
    assert "local_recipe_catalog" in script.text
    assert "/substitutions" in script.text
    assert 'id="pantryRecipeButton"' in page.text
    assert 'id="beverageForm"' in page.text
    assert "{id:'cocktails',title:'Cócteles'" in script.text
    assert "{id:'juices',title:'Jugos y refrescantes'" in script.text
    assert "recipe-category-grid" in script.text
    for asset in (
        "dog-banana-oat-treats.jpg", "dog-pumpkin-oat-biscuits.png", "dog-blueberry-yogurt-bites.png", "dog-chicken-carrot-meatballs.png",
        "cat-cooked-chicken-bites.jpg", "cat-cooked-salmon-flakes.png", "cat-turkey-mini-patties.png", "cat-egg-chicken-bites.png",
        "ferret-cooked-turkey-bites.jpg", "ferret-chicken-heart-bites.png", "ferret-cooked-egg-bites.png", "ferret-cooked-beef-bites.png",
    ):
        assert asset in worker.text
        assert client.get(f"/assets/roxy_home/recipes/pets/{asset}").status_code == 200
    assert ".pet-recipe-context[hidden]" in style.text
    assert "para perros" in script.text and "para gatos" in script.text and "para hurones" in script.text
    assert "dataset.recipeCategory" in script.text
    assert "Desayunos" in script.text and "Pastas y fideos" in script.text and "Postres" in script.text and "Café y calientes" in script.text
    assert "recipeCategoryId" in script.text
    assert 'id="recipeSearch"' in page.text
    assert "recipeCategories" in script.text
    assert "coffee_hot" in script.text
    assert "bowls_salads" in script.text
    assert "setup.open=true" in script.text
    assert "setup.classList.toggle('has-plan',Boolean(plan))" in script.text
    assert 'id="recipePersonalForm"' in page.text
    assert 'id="deleteRecipeButton"' in page.text
    assert "deleteCurrentRecipe" in script.text
    assert "method:'DELETE'" in script.text
    assert "¿Eliminar" in script.text
    assert 'id="startTimerButton"' in page.text
    assert "createRecipeFromPantry" in script.text
    assert "saveRecipePersonalization" in script.text
    assert "/timers" in script.text
    assert "loadRecipeVideo" in script.text
    assert "createRecipeVideo" not in script.text
    assert "Video de esta receta" in script.text
    assert "Cuando empieces a cocinar" in script.text
    assert "recipe_video_status" in script.text
    assert "syncRecipeVideo" in script.text
    assert "/recipe-videos/" in script.text
    assert "clip.step_indices" in script.text
    assert "clipMatchesStep" in script.text
    assert "las guardará y las reutilizará para todos" in script.text
    dockerfile = (roxy_home_service.ASSETS_DIR.parent / "Dockerfile.roxy-home").read_text(encoding="utf-8")
    assert "COPY assets/roxy_home/products ./assets/roxy_home/products" in dockerfile
    assert "COPY assets/roxy_home/recipes ./assets/roxy_home/recipes" in dockerfile
    assert "COPY assets/roxy_home/recipe_categories ./assets/roxy_home/recipe_categories" in dockerfile
    assert "COPY assets/roxy_home/recipe_custom ./assets/roxy_home/recipe_custom" in dockerfile
    assert "ROXY_HOME_ACCOUNTS_PATH=/var/data/roxy_home/accounts.json" in dockerfile
    assert "ROXY_HOME_VIDEO_LIBRARY_PATH=/var/data/roxy_home/recipe_video_library.json" in dockerfile
    assert "ROXY_HOME_VIDEO_MEDIA_DIR=/var/data/roxy_home/recipe_videos" in dockerfile
    assert "ROXY_HOME_RECIPE_LIBRARY_PATH=/var/data/roxy_home/recipe_library.sqlite" in dockerfile
    assert "COPY assets/roxy_home/home-hero-plant.png ./assets/roxy_home/home-hero-plant.png" in dockerfile
    assert "COPY assets/roxy_avatar_card.jpg ./assets/roxy_avatar_card.jpg" in dockerfile
    assert "ROXY_HOME_RECIPE_PHOTO_DIR=/var/data/roxy_home/recipe_photos" in dockerfile
    assert "/v1/home-food/recipe-photo?v=4&title=" in script.text
    assert "icon:'salad'" not in script.text
    assert "hydrateRecipeImage" in script.text
    assert "seenSavedTitles" in script.text
    assert "para personas" in script.text
    assert "para perros" in script.text
    for asset in ("pan-cubano.jpg", "cafe-americano.jpg", "cafe-con-canela.jpg", "affogato.jpg"):
        assert (roxy_home_service.ASSETS_DIR / "roxy_home" / "recipe_custom" / asset).is_file()
    assert "/assets/roxy_home/recipe_categories/" not in script.text
    for asset in ("pizza.png", "pasta.png", "bread.png", "soup-salad.png", "dessert.png", "drinks.png"):
        assert f"/assets/roxy_home/recipes/{asset}" in worker.text
        assert client.get(f"/assets/roxy_home/recipes/{asset}").status_code == 200
    for asset in ("breakfast.jpg", "proteins.jpg", "rice-pasta.jpg", "soups-bowls.jpg", "baked.jpg", "desserts.jpg", "coffee.jpg", "juices-smoothies.jpg"):
        assert f"/assets/roxy_home/recipe_categories/{asset}?v=1" not in worker.text
        assert client.get(f"/assets/roxy_home/recipe_categories/{asset}").status_code == 200


def test_shopping_api_crud_complete_history_and_user_isolation(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer shopping-test-key"}

    created = client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Leche", "quantity": 1, "unit": "litro", "category": "FOOD"},
    )
    item_id = created.json()["item"]["id"]
    updated = client.patch(f"/v1/shopping/robert/{item_id}", headers=headers, json={"quantity": 3})
    private = client.post("/v1/shopping/alice", headers=headers, json={"name": "Privado"})
    completed = client.post("/v1/shopping/robert/complete", headers=headers)
    snapshot = client.get("/v1/shopping/robert", headers=headers)
    alice = client.get("/v1/shopping/alice", headers=headers)

    assert created.status_code == 201
    assert updated.json()["item"]["quantity"] == 3
    assert private.status_code == 201
    assert completed.json()["count"] == 1
    assert snapshot.json()["items"] == []
    assert snapshot.json()["history"][0]["items"][0]["name"] == "Leche"
    assert alice.json()["items"][0]["name"] == "Privado"


def test_shopping_memory_learns_habitual_products_privately(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")
    store.add("robert", "Leche", quantity=2, unit="litro", category="FOOD")
    store.add("robert", "Pan", unit="paquete", category="FOOD")
    store.complete_purchase("robert")
    store.add("robert", "Leche", unit="litro", category="FOOD")
    store.complete_purchase("robert")
    store.add("alice", "Café privado", unit="bolsa", category="FOOD")
    store.complete_purchase("alice")

    robert = store.snapshot("robert")["habitual_products"]
    alice = store.snapshot("alice")["habitual_products"]

    assert robert[0]["name"] == "Leche"
    assert robert[0]["purchase_count"] == 2
    assert robert[0]["unit"] == "litro"
    assert {row["name"] for row in robert} == {"Leche", "Pan"}
    assert [row["name"] for row in alice] == ["Café privado"]


def test_voice_product_wrappers_are_removed_from_names_and_legacy_rows(tmp_path):
    path = tmp_path / "shopping.json"
    store = ShoppingListStore(path)
    created = store.add("robert", "agrega a la lista de compras detergente de lavar")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["items"].append(
        {
            "id": "legacy",
            "user_id": "robert",
            "name": "a la lista gel de cejas",
            "quantity": 1,
            "unit": "unidad",
            "category": "GENERAL",
            "status": "PENDING",
        }
    )
    path.write_text(json.dumps(raw), encoding="utf-8")

    names = {row["name"] for row in store.list_items("robert")}

    assert created["name"] == "detergente de lavar"
    assert normalize_shopping_name("a la lista de compras azúcar") == "azúcar"
    assert names == {"detergente de lavar", "gel de cejas"}


def test_mobile_session_cookie_is_httponly_secure_and_bound_to_user(monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")

    paired = client.post(
        "/v1/shopping/session/robert",
        headers={"Authorization": "Bearer shopping-test-key"},
    )
    denied = client.get("/v1/shopping/alice")

    cookie = paired.headers["set-cookie"]
    assert paired.status_code == 200
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "Max-Age=31536000" in cookie
    assert "shopping-test-key" not in cookie
    assert denied.status_code == 403


def test_roxy_home_is_a_separate_app_surface(monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-test-key")
    client = TestClient(roxy_home_service.app)

    assert client.get("/", follow_redirects=False).headers["location"] == "/home"
    assert client.get("/home").status_code == 200
    assert client.get("/home-sw.js").headers["service-worker-allowed"] == "/home"
    assert client.get("/health").json()["service"] == "roxy-home"
    assert client.get("/health").json()["video_prompt_version"] == 7
    assert client.get("/_stcore/health").status_code == 404
    assert client.get("/roxy-mobile").status_code == 404


def test_roxy_home_shared_elevenlabs_agent_can_read_and_update_shopping_list(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "agent_shared_roxy")
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    client.post(
        "/v1/shopping/session/robert",
        headers={"Authorization": "Bearer shopping-test-key"},
    )

    session = client.get("/v1/assistant/session/robert")
    command = client.post(
        "/v1/assistant/command/robert",
        json={"text": "agrega pan a mi lista de compra"},
    )
    shopping = client.get("/v1/shopping/robert")
    removed = client.post(
        "/v1/assistant/command/robert",
        json={"text": "quita pan de mi lista de compras"},
    )
    after_remove = client.get("/v1/shopping/robert")

    assert session.status_code == 200
    assert session.json()["provider"] == "ElevenLabs"
    assert session.json()["agent_id"] == "agent_shared_roxy"
    assert session.json()["voice_mode"] == "public_websocket"
    assert session.json()["connection_type"] == "websocket"
    assert command.status_code == 200
    assert command.json()["ok"] is True
    assert command.json()["agent"] == "shopping"
    assert "pan" in command.json()["message"].lower()
    assert shopping.json()["items"][0]["name"].lower() == "pan"
    assert removed.json()["intent"] == "shopping_remove"
    assert "pan" in removed.json()["message"].lower()
    assert after_remove.json()["items"] == []


def test_recipe_library_and_guided_cooking_api_are_private_and_persistent(tmp_path, monkeypatch):
    from tools import roxy_home_service

    class FakeHomeAI:
        def generate_recipe(self, prompt, snapshot, *, deep=False):
            return {
                "title": "Pan casero",
                "description": "Pan fácil",
                "kind": "bread",
                "servings": 4,
                "ingredients": [{"name": "Harina", "quantity": 3, "unit": "tazas"}],
                "steps": ["Mezcla la masa", "Hornea el pan"],
                "allergen_notes": [],
            }

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_HOME_RECIPE_LIBRARY_PATH", str(tmp_path / "recipe-library.sqlite"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    created = client.post(
        "/v1/home-food/robert/recipes",
        headers=headers,
        # An uncommon request verifies that the API still reaches OpenAI when
        # the expanded local catalog has no confident match.
        json={"prompt": "Hazme una injera etíope", "mode": "routine"},
    )
    recipe_id = created.json()["recipe"]["id"]
    beverage = client.post(
        "/v1/home-food/robert/recipes",
        headers=headers,
        json={"prompt": "Hazme un cóctel", "mode": "routine", "recipe_type": "alcoholic"},
    )
    personalized = client.patch(
        f"/v1/home-food/robert/recipes/{recipe_id}",
        headers=headers,
        json={
            "favorite": True,
            "user_notes": "Usar menos sal",
            "photo_data_url": "data:image/png;base64,aGVsbG8=",
        },
    )
    started = client.post(
        f"/v1/home-food/robert/recipes/{recipe_id}/cooking-sessions",
        headers=headers,
    )
    session_id = started.json()["session"]["id"]
    timer = client.post(
        f"/v1/home-food/robert/cooking-sessions/{session_id}/timers",
        headers=headers,
        json={"duration_seconds": 300, "label": "Horno"},
    )
    advanced = client.post(
        f"/v1/home-food/robert/cooking-sessions/{session_id}",
        headers=headers,
        json={"action": "next"},
    )
    private = client.get(
        f"/v1/home-food/alice/cooking-sessions/{session_id}",
        headers=headers,
    )
    snapshot = client.get("/v1/home-food/robert", headers=headers)

    assert created.status_code == 201
    assert created.json()["recipe"]["kind"] == "bread"
    assert beverage.json()["recipe"]["kind"] == "drink"
    assert beverage.json()["recipe"]["drink_type"] == "alcoholic"
    assert personalized.json()["recipe"]["favorite"] is True
    assert personalized.json()["recipe"]["user_notes"] == "Usar menos sal"
    assert timer.status_code == 201
    assert timer.json()["session"]["timers"][0]["label"] == "Horno"
    assert started.json()["current_step"] == "Mezcla la masa"
    assert advanced.json()["current_step"] == "Hornea el pan"
    assert snapshot.json()["recipes"][0]["title"] == "Pan casero"
    assert snapshot.json()["cooking_sessions"][0]["step_index"] == 1
    assert private.status_code == 404


def test_roxy_voice_preserves_natural_quantities_and_units(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    response = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Agrega dos paquetes de agua, medio kilo de arroz y una docena de huevos"},
    )

    assert response.status_code == 200
    rows = response.json()["snapshot"]["items"]
    structured = {row["name"].lower(): (row["quantity"], row["unit"], row["category"]) for row in rows}
    assert structured == {
        "agua": (2, "paquete", "BEVERAGES"),
        "arroz": (0.5, "kilo", "PANTRY"),
        "huevos": (1, "docena", "DAIRY_EGGS"),
    }


def test_roxy_voice_saves_recipe_adds_ingredients_and_guides_steps(tmp_path, monkeypatch):
    from tools import roxy_home_service

    class FakeHomeAI:
        def generate_recipe(self, prompt, snapshot, *, deep=False):
            return {
                "title": "Limonada",
                "description": "Bebida fresca",
                "kind": "drink",
                "servings": 2,
                "ingredients": [{"name": "Limón", "quantity": 4, "unit": "unidad"}],
                "steps": ["Exprime los limones", "Mezcla con agua"],
                "allergen_notes": [],
            }

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    recipe = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Dame una limonada"},
    )
    ingredients = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Agrega los ingredientes de esta receta a mi carrito"},
    )
    guide = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Guíame paso a paso"},
    )
    next_step = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Siguiente paso"},
    )
    timer = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Pon un temporizador de cinco minutos"},
    )
    time_left = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Cuánto tiempo queda"},
    )

    assert recipe.json()["data"]["recipe"]["kind"] == "drink"
    assert recipe.json()["must_speak"] is True
    assert recipe.json()["speech"] == recipe.json()["message"]
    assert "Preparación:" in recipe.json()["speech"]
    assert ingredients.json()["intent"] == "recipe_to_shopping"
    assert recipe.json()["data"]["generation_mode"] == "voice_local_recipe_catalog"
    assert ingredients.json()["snapshot"]["pending_count"] == 4
    assert guide.json()["data"]["cooking"]["current_step"].startswith("Lava la fruta")
    assert next_step.json()["data"]["cooking"]["current_step"].startswith("Corta todo en trozos")
    assert timer.json()["intent"] == "cooking_timer_set"
    assert timer.json()["data"]["timer"]["duration_seconds"] == 300
    assert time_left.json()["intent"] == "cooking_timer_query"
    assert "minutos" in time_left.json()["message"]
def test_ambiguous_shopping_product_requires_clarification(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-clarify-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_CONVERSATION_PATH", str(tmp_path / "conversation.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    client.post("/v1/shopping/session/robert", headers={"Authorization": "Bearer shopping-clarify-key"})

    question = client.post("/v1/assistant/command/robert", json={"text": "agrega pasta"})
    before = client.get("/v1/shopping/robert")
    answer = client.post("/v1/assistant/command/robert", json={"text": "la de dientes"})
    after = client.get("/v1/shopping/robert")

    assert question.status_code == 200
    assert question.json()["intent"] == "shopping_clarify"
    assert "pasta dental" in question.json()["message"].lower()
    assert "pasta para comer" in question.json()["message"].lower()
    assert before.json()["items"] == []
    assert answer.status_code == 200
    assert answer.json()["intent"] == "shopping_add"
    assert after.json()["items"][0]["name"] == "Pasta dental"
    assert after.json()["items"][0]["unit"] == "tubo"
    assert after.json()["items"][0]["category"] == "PERSONAL"


def test_explicit_toothpaste_is_canonicalized_without_clarification(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-dental-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_CONVERSATION_PATH", str(tmp_path / "conversation.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    client.post("/v1/shopping/session/robert", headers={"Authorization": "Bearer shopping-dental-key"})

    response = client.post("/v1/assistant/command/robert", json={"text": "agrega pasta de dientes"})
    item = client.get("/v1/shopping/robert").json()["items"][0]

    assert response.status_code == 200
    assert response.json()["intent"] == "shopping_add"
    assert item["name"] == "Pasta dental"
    assert item["unit"] == "tubo"
    assert item["category"] == "PERSONAL"


def test_old_calendar_voice_rows_are_removed_from_shopping_snapshot(tmp_path):
    state_path = tmp_path / "shopping.json"
    state_path.write_text(json.dumps({
        "schema_version": 5,
        "items": [
            {
                "id": "bad-calendar-row", "user_id": "robert",
                "name": "al calendario que mañana llevo a Bella al veterinario a las 2:00 p.m.",
                "quantity": 1, "unit": "unidad", "category": "OTHER",
                "status": "PENDING", "source": "elevenlabs_voice",
            },
            {
                "id": "real-product", "user_id": "robert", "name": "Pan",
                "quantity": 1, "unit": "unidad", "category": "BAKERY",
                "status": "PENDING", "source": "elevenlabs_voice",
            },
        ],
        "trips": [], "product_memory": {}, "user_revisions": {},
    }), encoding="utf-8")

    snapshot = ShoppingListStore(state_path).snapshot("robert")

    assert [item["name"] for item in snapshot["items"]] == ["Pan"]


def test_dulce_de_leche_and_ice_cream_are_distinct_products(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-dessert-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_CONVERSATION_PATH", str(tmp_path / "conversation.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    client.post("/v1/shopping/session/robert", headers={"Authorization": "Bearer shopping-dessert-key"})

    caramel = client.post("/v1/assistant/command/robert", json={"text": "Roxy agrega dulce de leche"})
    ice_cream = client.post("/v1/assistant/command/robert", json={"text": "Roxy agrega elado de dulce de leche"})
    items = client.get("/v1/shopping/robert").json()["items"]
    by_name = {item["name"]: item for item in items}

    assert caramel.json()["intent"] == "shopping_add"
    assert ice_cream.json()["intent"] == "shopping_add"
    assert by_name["Dulce de leche"]["unit"] == "lata"
    assert by_name["Dulce de leche"]["category"] == "PANTRY"
    assert by_name["Helado de dulce de leche"]["unit"] == "envase"
    assert by_name["Helado de dulce de leche"]["category"] == "FROZEN"


def test_roxy_learns_private_shopping_vocabulary_and_reuses_it(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-vocabulary-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_CONVERSATION_PATH", str(tmp_path / "conversation.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    client.post("/v1/shopping/session/robert", headers={"Authorization": "Bearer shopping-vocabulary-key"})

    taught = client.post(
        "/v1/assistant/command/robert",
        json={"text": "Roxy, cuando digo las blancas, me refiero a empapadores absorbentes para mascota"},
    )
    added = client.post("/v1/assistant/command/robert", json={"text": "Agrega las blancas"})
    item = client.get("/v1/shopping/robert").json()["items"][0]

    assert taught.status_code == 200
    assert taught.json()["intent"] == "shopping_teach_alias"
    assert taught.json()["data"]["learned_alias"]["source"] == "user_correction"
    assert added.json()["intent"] == "shopping_add"
    assert item["name"] == "Empapadores absorbentes para mascota"
    assert item["category"] == "PETS"
