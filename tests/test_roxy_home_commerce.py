from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from roxy_os.home_commerce import HomeCommerceStore


def _client(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "food.json"))
    monkeypatch.setenv("ROXY_HOME_COMMERCE_PATH", str(tmp_path / "commerce.json"))
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    roxy_home_service._RATE_STATE.clear()
    return TestClient(roxy_home_service.app), {"Authorization": "Bearer home-test-key"}


def test_affiliate_purchase_requires_confirmation_and_uses_personal_profile(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("ROXY_HOME_AMAZON_ASSOCIATE_TAG", "roxyhome-20")

    created = client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Pan", "quantity": 2, "unit": "paquete", "category": "FOOD"},
    )
    profile = client.put(
        "/v1/home-commerce/robert/profile",
        headers=headers,
        json={
            "objective": "organic",
            "organic_preference": "required",
            "favorite_retailers": ["Amazon"],
            "favorite_brands": [],
            "avoided_brands": [],
            "dietary_labels": ["sin gluten"],
            "allow_substitutions": False,
            "postal_code": "33101",
        },
    )
    prepared = client.post(
        "/v1/home-commerce/robert/preparations",
        headers=headers,
        json={"source": "shopping", "provider_ids": ["amazon"]},
    )
    preparation = prepared.json()["preparation"]
    blocked = client.post(
        f"/v1/home-commerce/robert/preparations/{preparation['id']}/checkout",
        headers=headers,
        json={"provider_id": "amazon", "confirmed": False},
    )
    checkout = client.post(
        f"/v1/home-commerce/robert/preparations/{preparation['id']}/checkout",
        headers=headers,
        json={"provider_id": "amazon", "confirmed": True},
    )

    assert created.status_code == 201
    assert profile.status_code == 200
    assert prepared.status_code == 201
    assert preparation["items"][0]["query"] == "orgánico Pan sin gluten"
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "CONFIRMATION_REQUIRED"
    assert checkout.status_code == 200
    link = checkout.json()["links"][0]["url"]
    query = parse_qs(urlparse(link).query)
    assert query["tag"] == ["roxyhome-20"]
    assert query["k"] == ["orgánico Pan sin gluten"]
    assert checkout.json()["status"] == "READY_FOR_REVIEW"
    assert checkout.json()["handoff"]["status"] == "READY_FOR_REVIEW"

    activity = client.get("/v1/home-commerce/robert", headers=headers).json()["activity"]
    assert activity["handoff_count"] == 1
    assert activity["provider_counts"] == {"amazon": 1}
    assert activity["recent"][0]["source_title"] == "Lista de compras de Roxy Home"
    assert "owner_key" not in activity["recent"][0]


def test_repeated_checkout_does_not_double_count_handoff(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("ROXY_HOME_AMAZON_ASSOCIATE_TAG", "roxyhome-20")
    client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Café", "quantity": 1, "unit": "bolsa", "category": "FOOD"},
    )
    preparation = client.post(
        "/v1/home-commerce/robert/preparations",
        headers=headers,
        json={"source": "shopping", "provider_ids": ["amazon"]},
    ).json()["preparation"]
    endpoint = f"/v1/home-commerce/robert/preparations/{preparation['id']}/checkout"

    first = client.post(endpoint, headers=headers, json={"provider_id": "amazon", "confirmed": True})
    second = client.post(endpoint, headers=headers, json={"provider_id": "amazon", "confirmed": True})
    activity = client.get("/v1/home-commerce/robert", headers=headers).json()["activity"]

    assert first.status_code == second.status_code == 200
    assert first.json()["handoff"]["id"] == second.json()["handoff"]["id"]
    assert activity["handoff_count"] == 1


def test_commerce_profiles_are_isolated_per_authenticated_person(tmp_path):
    store = HomeCommerceStore(tmp_path / "commerce.json")
    store.update_profile(
        "member:robert",
        {
            "objective": "lowest_price",
            "organic_preference": "no_preference",
            "favorite_retailers": ["Walmart"],
            "favorite_brands": [],
            "avoided_brands": [],
            "dietary_labels": [],
            "allow_substitutions": True,
            "postal_code": "33101",
        },
    )
    store.update_profile(
        "member:roxy",
        {
            "objective": "organic",
            "organic_preference": "required",
            "favorite_retailers": ["Thrive Market"],
            "favorite_brands": [],
            "avoided_brands": [],
            "dietary_labels": ["vegano"],
            "allow_substitutions": False,
            "postal_code": "33101",
        },
    )

    assert store.profile("member:robert")["objective"] == "lowest_price"
    assert store.profile("member:roxy")["objective"] == "organic"
    assert store.profile("member:robert")["favorite_retailers"] == ["Walmart"]


def test_handoff_activity_is_private_and_does_not_claim_a_purchase(tmp_path):
    store = HomeCommerceStore(tmp_path / "commerce.json")
    preparation = store.save_preparation(
        "member:robert",
        "household",
        source="shopping",
        source_title="Lista de Roberto",
        items=[{"name": "Pan"}],
        providers=["amazon"],
    )
    store.record_handoff(
        "member:robert",
        preparation["id"],
        provider_id="amazon",
        provider_name="Amazon",
        mode="product_links",
        link_count=1,
    )

    robert = store.activity("member:robert")
    roxy = store.activity("member:roxy")

    assert robert["handoff_count"] == 1
    assert robert["recent"][0]["status"] == "READY_FOR_REVIEW"
    assert "purchase" not in robert["recent"][0]
    assert roxy["handoff_count"] == 0


def test_roxy_can_prepare_but_not_complete_a_purchase_by_voice(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Arroz", "quantity": 1, "unit": "bolsa", "category": "FOOD"},
    )

    response = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, prepara mi compra"},
    )

    assert response.status_code == 200
    assert response.json()["intent"] == "commerce_prepare"
    assert response.json()["data"]["preparation"]["items"][0]["name"] == "Arroz"
    assert "no pagaré" in response.json()["message"]


def test_instacart_affiliate_link_is_fallback_without_developer_key(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    monkeypatch.delenv("ROXY_HOME_INSTACART_API_KEY", raising=False)
    monkeypatch.setenv("ROXY_HOME_INSTACART_AFFILIATE_URL", "https://instacart.pxf.io/roxy-home")
    client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Leche", "quantity": 1, "unit": "litro", "category": "FOOD"},
    )
    prepared = client.post(
        "/v1/home-commerce/robert/preparations",
        headers=headers,
        json={"source": "shopping", "provider_ids": ["instacart"]},
    )
    preparation = prepared.json()["preparation"]
    checkout = client.post(
        f"/v1/home-commerce/robert/preparations/{preparation['id']}/checkout",
        headers=headers,
        json={"provider_id": "instacart", "confirmed": True},
    )

    assert prepared.status_code == 201
    assert checkout.status_code == 200
    assert checkout.json()["mode"] == "affiliate_link"
    assert checkout.json()["links"] == [
        {"label": "Abrir Instacart", "url": "https://instacart.pxf.io/roxy-home"}
    ]


def test_recipe_ingredients_can_be_prepared_without_adding_fake_products(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    recipe = client.post(
        "/v1/home-food/robert/recipes",
        headers=headers,
        json={"prompt": "Pan casero sencillo", "mode": "routine"},
    ).json()["recipe"]

    prepared = client.post(
        "/v1/home-commerce/robert/preparations",
        headers=headers,
        json={"source": "recipe", "recipe_id": recipe["id"], "provider_ids": ["amazon"]},
    )
    shopping = client.get("/v1/shopping/robert", headers=headers)
    configuration = client.get("/v1/home-commerce/robert", headers=headers)

    assert prepared.status_code == 201
    assert prepared.json()["preparation"]["source"] == "recipe"
    assert prepared.json()["preparation"]["items"]
    assert shopping.json()["items"] == []
    assert "ROXY_HOME_AMAZON_ASSOCIATE_TAG" not in str(configuration.json())


def test_home_commerce_controls_are_connected_to_real_endpoints():
    page = open("assets/roxy_list.html", encoding="utf-8").read()
    script = open("assets/roxy_list.js", encoding="utf-8").read()

    assert 'id="prepareShoppingButton"' in page
    assert 'id="commerceProfileForm"' in page
    assert 'id="commerceDialog"' in page
    assert 'id="commerceConfirmCheck"' in page
    assert 'id="commerceConfirmButton"' in page
    assert 'id="commerceRecent"' in page
    assert 'id="commerceProviderDisclosure"' in page
    assert "/v1/home-commerce/" in script
    assert "preparePurchase('recipe'" in script
    assert "confirmed:true" in script
    assert "confirmProviderHandoff" in script
    assert "dataset.externalCheckout" in script
    assert "Revisar productos y pagar en" in script
    assert "Última compra preparada" in script


def test_impact_template_supports_anonymous_sub_id(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "ROXY_HOME_WALMART_AFFILIATE_LINK_TEMPLATE",
        "https://track.example/click?sub={sub_id}&dest={destination}",
    )
    client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Arroz", "quantity": 1, "unit": "bolsa", "category": "FOOD"},
    )
    preparation = client.post(
        "/v1/home-commerce/robert/preparations",
        headers=headers,
        json={"source": "shopping", "provider_ids": ["walmart"]},
    ).json()["preparation"]
    result = client.post(
        f"/v1/home-commerce/robert/preparations/{preparation['id']}/checkout",
        headers=headers,
        json={"provider_id": "walmart", "confirmed": True},
    ).json()
    query = parse_qs(urlparse(result["links"][0]["url"]).query)

    assert query["sub"] == [preparation["tracking_id"]]
    assert "robert" not in result["links"][0]["url"]


def test_amazon_required_disclosure_is_returned_near_links(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("ROXY_HOME_AMAZON_ASSOCIATE_TAG", "roxyhome-20")
    client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Aceite", "quantity": 1, "unit": "botella", "category": "FOOD"},
    )
    preparation = client.post(
        "/v1/home-commerce/robert/preparations",
        headers=headers,
        json={"source": "shopping", "provider_ids": ["amazon"]},
    ).json()["preparation"]
    result = client.post(
        f"/v1/home-commerce/robert/preparations/{preparation['id']}/checkout",
        headers=headers,
        json={"provider_id": "amazon", "confirmed": True},
    ).json()
    home_commerce = client.get("/v1/home-commerce/robert", headers=headers).json()

    assert result["provider_disclosure"] == "As an Amazon Associate I earn from qualifying purchases."
    assert "As an Amazon Associate I earn from qualifying purchases." in home_commerce["disclosure"]
