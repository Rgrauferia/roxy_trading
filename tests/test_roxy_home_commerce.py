from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from roxy_os.home_commerce import HomeCommerceStore
from roxy_os.home_price_recommendations import recommend_prices


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
    assert 'id="priceRecommendations"' in page
    assert 'id="refreshPricesButton"' in page
    assert "/v1/home-commerce/" in script
    assert "/recommendations" in script
    assert "reviewRetailOffer" in script
    assert "preparePurchase('recipe'" in script
    assert "confirmed:true" in script
    assert "confirmProviderHandoff" in script
    assert "dataset.externalCheckout" in script
    assert "Revisar productos y pagar en" in script
    assert "Última compra preparada" in script


def test_price_recommendations_only_claim_savings_for_comparable_units():
    observed_at = datetime.now(timezone.utc).isoformat()
    items = [{"name": "Leche", "quantity": 1, "unit": "galón"}]
    offers = [
        {
            "item_name": "Leche",
            "retailer_id": "walmart",
            "retailer_name": "Walmart",
            "product_title": "Leche entera",
            "price": 3.50,
            "unit_price": 0.22,
            "comparison_unit": "fl oz",
            "currency": "USD",
            "product_url": "https://www.walmart.com/ip/1",
            "observed_at": observed_at,
            "availability": "available",
        },
        {
            "item_name": "Leche",
            "retailer_id": "target",
            "retailer_name": "Target",
            "product_title": "Leche entera",
            "price": 4.30,
            "unit_price": 0.27,
            "comparison_unit": "fl oz",
            "currency": "USD",
            "product_url": "https://www.target.com/p/1",
            "observed_at": observed_at,
            "availability": "available",
        },
        {
            "item_name": "Leche",
            "retailer_id": "other",
            "retailer_name": "Otra",
            "product_title": "Leche individual",
            "price": 1.00,
            "unit_price": 1.00,
            "comparison_unit": "count",
            "currency": "USD",
            "product_url": "https://example.com/leche",
            "observed_at": observed_at,
            "availability": "available",
        },
    ]
    result = recommend_prices(
        items,
        offers,
        {"objective": "lowest_price", "organic_preference": "no_preference"},
    )

    recommendation = result["recommendations"][0]
    assert recommendation["retailer_name"] == "Walmart"
    assert recommendation["savings_per_unit"] == 0.05
    assert recommendation["comparison_retailer"] == "Target"
    assert "Otra" not in " ".join(recommendation["reasons"])


def test_required_organic_never_falls_back_to_conventional_offer():
    result = recommend_prices(
        [{"name": "Pan", "quantity": 1, "unit": "paquete"}],
        [
            {
                "item_name": "Pan",
                "retailer_id": "walmart",
                "retailer_name": "Walmart",
                "product_title": "Pan blanco",
                "price": 2,
                "currency": "USD",
                "product_url": "https://www.walmart.com/ip/2",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "availability": "available",
                "organic_certified": False,
            }
        ],
        {"objective": "organic", "organic_preference": "required"},
    )

    assert result["status"] == "NO_VERIFIED_PRICES"
    assert result["recommendations"] == []
    assert result["unpriced_items"] == ["Pan"]


def test_price_endpoint_returns_no_fake_prices_without_authorized_feed(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    monkeypatch.delenv("ROXY_HOME_PRICE_FEED_URL", raising=False)
    monkeypatch.delenv("ROXY_HOME_PRICE_FEED_API_KEY", raising=False)
    client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Leche", "quantity": 1, "unit": "galón", "category": "FOOD"},
    )

    response = client.get("/v1/home-commerce/robert/recommendations", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "PRICE_SOURCE_NOT_CONNECTED"
    assert response.json()["recommendations"] == []
    assert "precios inventados" in response.json()["message"]


def test_roxy_voice_can_explain_when_price_feed_is_not_connected(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    monkeypatch.delenv("ROXY_HOME_PRICE_FEED_URL", raising=False)
    monkeypatch.delenv("ROXY_HOME_PRICE_FEED_API_KEY", raising=False)
    client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Pan", "quantity": 1, "unit": "paquete", "category": "FOOD"},
    )

    response = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, ¿dónde está más barato comprar lo de mi lista?"},
    )

    assert response.status_code == 200
    assert response.json()["intent"] == "commerce_compare"
    assert response.json()["data"]["price_recommendations"]["recommendations"] == []
    assert "no inventaré precios" in response.json()["message"]


def test_price_endpoint_returns_ranked_live_offer_from_server_side_feed(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_PRICE_FEED_URL", "https://prices.example.com/search")
    monkeypatch.setenv("ROXY_HOME_PRICE_FEED_API_KEY", "server-only-secret")
    monkeypatch.setattr(
        roxy_home_service,
        "fetch_price_offers",
        lambda items, profile, config: [
            {
                "item_name": "Aguacate",
                "retailer_id": "walmart",
                "retailer_name": "Walmart",
                "product_title": "Aguacate Hass orgánico",
                "brand": "Fresh",
                "price": 1.25,
                "unit_price": 1.25,
                "comparison_unit": "unidad",
                "currency": "USD",
                "organic_certified": True,
                "product_url": "https://www.walmart.com/ip/avocado",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "availability": "available",
            }
        ],
    )
    client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Aguacate", "quantity": 2, "unit": "unidad", "category": "FOOD"},
    )

    response = client.get("/v1/home-commerce/robert/recommendations", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert response.json()["recommendations"][0]["retailer_name"] == "Walmart"
    assert response.json()["recommendations"][0]["price"] == 1.25
    assert "server-only-secret" not in response.text


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
