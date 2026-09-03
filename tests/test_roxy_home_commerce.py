from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from roxy_os.home_commerce import HomeCommerceStore, create_purchase_links, public_providers
from roxy_os.home_price_recommendations import (
    PriceFeedConfig,
    fetch_nearby_retailers,
    fetch_price_offers,
    recommend_prices,
)


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
    assert preparation["items"][0]["category"] == "BAKERY"
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "CONFIRMATION_REQUIRED"
    assert checkout.status_code == 200
    link = checkout.json()["links"][0]["url"]
    query = parse_qs(urlparse(link).query)
    assert query["tag"] == ["roxyhome-20"]
    assert query["k"] == ["organic gluten free bread 2 pack"]
    assert checkout.json()["links"][0]["quantity"] == 2
    assert checkout.json()["links"][0]["unit"] == "paquete"
    assert checkout.json()["links"][0]["category"] == "BAKERY"
    assert "Amazon.com" in checkout.json()["guidance"]
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
    assert 'id="prepareAmazonButton"' in page
    assert 'id="commerceProfileForm"' in page
    assert 'id="commerceDialog"' in page
    assert 'id="commerceConfirmCheck"' in page
    assert 'id="commerceConfirmButton"' in page
    assert 'id="commerceRecent"' in page
    assert 'id="commerceProviderDisclosure"' in page
    assert 'id="priceRecommendations"' in page
    assert 'id="refreshPricesButton"' in page
    assert 'id="priceAlerts"' in page
    assert 'id="nearbyRetailers"' in page
    assert 'id="commercePriceAlerts"' in page
    assert 'id="commercePriceDrop"' in page
    assert 'id="commerceUseLocation"' in page
    assert 'id="commerceClearLocation"' in page
    assert "/v1/home-commerce/" in script
    assert "/recommendations" in script
    assert "reviewRetailOffer" in script
    assert "offer.image_url" in script
    assert "preparePurchase('recipe'" in script
    assert "confirmed:true" in script
    assert "confirmProviderHandoff" in script
    assert "preparePurchase('shopping',null,'amazon')" in script
    assert "dataset.externalCheckout" in script
    assert "Revisar productos y pagar en" in script
    assert "commerce-product-link" in script
    assert "Ver en ${provider.name}" in script
    assert "result.guidance" in script
    assert "Última compra preparada" in script
    assert "renderPriceCoverage" in script
    assert "price_drop_percent" in script
    assert "retailers_checked" in script
    assert "navigator.geolocation.getCurrentPosition" in script
    assert "enableHighAccuracy:false" in script


def test_price_alert_preferences_and_history_are_private(tmp_path):
    store = HomeCommerceStore(tmp_path / "commerce.json")
    profile = store.update_profile(
        "member:robert",
        {
            "objective": "lowest_price",
            "organic_preference": "no_preference",
            "favorite_retailers": [],
            "favorite_brands": [],
            "avoided_brands": [],
            "dietary_labels": [],
            "allow_substitutions": True,
            "postal_code": "33101",
            "price_alerts_enabled": True,
            "price_drop_percent": 10,
        },
    )
    base = {
        "shopping_item": "Leche",
        "retailer_name": "Kroger",
        "product_title": "Leche entera 1 gal",
        "package_label": "1 gal",
        "comparison_unit": "fl oz",
        "currency": "USD",
        "product_url": "https://www.kroger.com/p/milk/1",
    }
    first = store.record_price_recommendations(
        "member:robert",
        [{**base, "price": 4.00, "unit_price": 0.04, "observed_at": "2026-08-23T12:00:00+00:00"}],
        alert_percent=10,
    )
    second = store.record_price_recommendations(
        "member:robert",
        [{**base, "price": 3.00, "unit_price": 0.03, "observed_at": "2026-08-24T12:00:00+00:00"}],
        alert_percent=10,
    )

    assert profile["price_alerts_enabled"] is True
    assert profile["price_drop_percent"] == 10
    assert first["new_alerts"] == []
    assert second["new_alerts"][0]["drop_percent"] == 25.0
    assert "Leche bajó 25 %" in second["new_alerts"][0]["message"]
    assert store.price_activity("member:robert")["observation_count"] == 2
    assert store.price_activity("member:roxy")["observation_count"] == 0


def test_approximate_location_requires_consent_and_is_rounded(tmp_path):
    store = HomeCommerceStore(tmp_path / "commerce.json")
    common = {
        "objective": "balanced",
        "organic_preference": "no_preference",
        "favorite_retailers": [],
        "favorite_brands": [],
        "avoided_brands": [],
        "dietary_labels": [],
        "allow_substitutions": True,
        "postal_code": "33101",
    }
    enabled = store.update_profile(
        "member:robert",
        {
            **common,
            "location_enabled": True,
            "latitude": 25.761681,
            "longitude": -80.191788,
            "location_accuracy_m": 18.6,
        },
    )
    disabled = store.update_profile("member:roxy", common)

    assert enabled["latitude"] == 25.762
    assert enabled["longitude"] == -80.192
    assert enabled["location_accuracy_m"] == 19
    assert enabled["location_updated_at"]
    assert disabled["location_enabled"] is False
    assert disabled["latitude"] is None


def test_price_alert_does_not_compare_different_package_metrics(tmp_path):
    store = HomeCommerceStore(tmp_path / "commerce.json")
    common = {
        "shopping_item": "Huevos",
        "retailer_name": "Tienda",
        "product_title": "Huevos",
        "currency": "USD",
        "product_url": "https://example.com/eggs",
    }
    store.record_price_recommendations(
        "member:robert",
        [{**common, "package_label": "12 count", "price": 6, "observed_at": "2026-08-23T12:00:00+00:00"}],
    )
    result = store.record_price_recommendations(
        "member:robert",
        [{**common, "package_label": "6 count", "price": 2, "observed_at": "2026-08-24T12:00:00+00:00"}],
    )

    assert result["new_alerts"] == []


def test_instacart_discovers_nearby_retailers_without_exposing_key(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"retailers":[{"retailer_key":"publix","name":"Publix","retailer_logo_url":"https://example.com/publix.png"},{"retailer_key":"aldi","name":"ALDI"}]}'

    def fake_urlopen(request, timeout):
        assert timeout == 7
        assert "postal_code=90210" in request.full_url
        assert request.headers["Authorization"] == "Bearer instacart-server-secret"
        return Response()

    monkeypatch.setattr("roxy_os.home_price_recommendations.urllib.request.urlopen", fake_urlopen)
    retailers = fetch_nearby_retailers(
        {"postal_code": "90210"},
        config=PriceFeedConfig(
            url="",
            api_key="",
            timeout_seconds=7,
            instacart_api_key="instacart-server-secret",
        ),
    )

    assert [row["name"] for row in retailers] == ["Publix", "ALDI"]
    assert all(row["price_access"] == "in_instacart" for row in retailers)
    assert "instacart-server-secret" not in str(retailers)


def test_authorized_price_feed_receives_only_approximate_location(monkeypatch):
    import json

    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"offers":[]}'

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data.decode("utf-8")))
        return Response()

    monkeypatch.setenv("ROXY_HOME_PRICE_CACHE_SECONDS", "0")
    monkeypatch.setattr("roxy_os.home_price_recommendations.urllib.request.urlopen", fake_urlopen)
    offers = fetch_price_offers(
        [{"name": "Leche", "quantity": 1, "unit": "galón"}],
        {
            "postal_code": "33101",
            "location_enabled": True,
            "latitude": 25.761681,
            "longitude": -80.191788,
            "location_accuracy_m": 18.6,
        },
        config=PriceFeedConfig(url="https://prices.example.com/search", api_key="secret"),
    )

    assert offers == []
    assert captured["approximate_location"] == {
        "latitude": 25.762,
        "longitude": -80.192,
        "accuracy_m": 19,
    }
    assert set(captured) == {"postal_code", "approximate_location", "currency", "items"}


def test_amazon_searches_translate_common_spanish_products_and_keep_tag(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("ROXY_HOME_AMAZON_ASSOCIATE_TAG", "roxyhomeapp-20")
    client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Harina de trigo", "quantity": 1, "unit": "bolsa", "category": "FOOD"},
    )
    preparation = client.post(
        "/v1/home-commerce/robert/preparations",
        headers=headers,
        json={"source": "shopping", "provider_ids": ["amazon"]},
    ).json()["preparation"]
    checkout = client.post(
        f"/v1/home-commerce/robert/preparations/{preparation['id']}/checkout",
        headers=headers,
        json={"provider_id": "amazon", "confirmed": True},
    )

    assert checkout.status_code == 200
    link = checkout.json()["links"][0]
    query = parse_qs(urlparse(link["url"]).query)
    assert query["tag"] == ["roxyhomeapp-20"]
    assert query["k"] == ["all purpose flour 1 bag"]
    assert link["label"] == "Harina de trigo"


def test_amazon_favorite_brand_and_dietary_preferences_shape_search(tmp_path, monkeypatch):
    client, headers = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("ROXY_HOME_AMAZON_ASSOCIATE_TAG", "roxyhomeapp-20")
    client.put(
        "/v1/home-commerce/robert/profile",
        headers=headers,
        json={
            "objective": "favorites",
            "organic_preference": "preferred",
            "favorite_retailers": ["Amazon"],
            "favorite_brands": ["365 Everyday Value"],
            "avoided_brands": ["Marca X"],
            "dietary_labels": ["sin lactosa"],
            "allow_substitutions": True,
            "postal_code": "33101",
        },
    )
    client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Leche", "quantity": 1, "unit": "galón", "category": "FOOD"},
    )
    preparation = client.post(
        "/v1/home-commerce/robert/preparations",
        headers=headers,
        json={"source": "shopping", "provider_ids": ["amazon"]},
    ).json()["preparation"]
    checkout = client.post(
        f"/v1/home-commerce/robert/preparations/{preparation['id']}/checkout",
        headers=headers,
        json={"provider_id": "amazon", "confirmed": True},
    ).json()

    link = checkout["links"][0]
    assert parse_qs(urlparse(link["url"]).query)["k"] == [
        "organic lactose free 365 Everyday Value milk 1 gallon"
    ]
    assert link["avoided_brands"] == ["Marca X"]


def test_affiliate_application_status_is_visible_but_does_not_enable_provider(monkeypatch):
    monkeypatch.delenv("ROXY_HOME_WALMART_AFFILIATE_LINK_TEMPLATE", raising=False)
    monkeypatch.setenv("ROXY_HOME_WALMART_AFFILIATE_STATUS", "in_review")

    walmart = next(row for row in public_providers() if row["id"] == "walmart")

    assert walmart["configured"] is False
    assert walmart["connection_status"] == "in_review"
    assert walmart["status_label"] == "En revisión"
    assert "aprobarla" in walmart["next_step"]


def test_configured_provider_is_ready_even_if_old_status_says_in_review(monkeypatch):
    monkeypatch.setenv("ROXY_HOME_WALMART_AFFILIATE_STATUS", "in_review")
    monkeypatch.setenv(
        "ROXY_HOME_WALMART_AFFILIATE_LINK_TEMPLATE",
        "https://tracking.example/click?dest={destination}",
    )

    walmart = next(row for row in public_providers() if row["id"] == "walmart")

    assert walmart["configured"] is True
    assert walmart["connection_status"] == "ready"
    assert walmart["status_label"] == "Listo"


def test_furniture_catalog_sources_create_official_search_links_without_claiming_prices():
    preparation = {
        "providers": ["ikea", "wayfair", "west_elm", "article"],
        "items": [{"name": "sillón moderno de roble", "query": "sillón moderno de roble", "quantity": 1, "unit": "unidad", "category": "HOUSEHOLD"}],
    }

    expected_hosts = {
        "ikea": "www.ikea.com",
        "wayfair": "www.wayfair.com",
        "west_elm": "www.westelm.com",
        "article": "www.article.com",
    }
    for provider_id, host in expected_hosts.items():
        result = create_purchase_links(provider_id, preparation)
        assert urlparse(result["links"][0]["url"]).netloc == host
        assert "no afirma disponibilidad ni precio" in result["provider_disclosure"]


def test_furniture_sources_distinguish_catalog_from_affiliate_connection(monkeypatch):
    monkeypatch.delenv("ROXY_HOME_WAYFAIR_AFFILIATE_LINK_TEMPLATE", raising=False)
    catalog = next(row for row in public_providers() if row["id"] == "wayfair")

    assert catalog["configured"] is True
    assert catalog["affiliate_connected"] is False
    assert catalog["connection_status"] == "catalog_ready"
    assert catalog["status_label"] == "Catálogo listo"

    monkeypatch.setenv(
        "ROXY_HOME_WAYFAIR_AFFILIATE_LINK_TEMPLATE",
        "https://tracking.example/click?destination={destination}&subid={sub_id}",
    )
    affiliate = next(row for row in public_providers() if row["id"] == "wayfair")

    assert affiliate["affiliate_connected"] is True
    assert affiliate["connection_status"] == "affiliate_ready"
    assert affiliate["status_label"] == "Afiliado listo"


def test_furniture_affiliate_template_wraps_exact_official_destination(monkeypatch):
    monkeypatch.setenv(
        "ROXY_HOME_ARTICLE_AFFILIATE_LINK_TEMPLATE",
        "https://tracking.example/click?destination={destination}&query={query}&subid={sub_id}",
    )
    preparation = {
        "providers": ["article"],
        "tracking_id": "renueva-project-1",
        "items": [
            {
                "name": "sofá modular de lino",
                "query": "sofá modular de lino",
                "quantity": 1,
                "unit": "unidad",
                "category": "HOUSEHOLD",
            }
        ],
    }

    result = create_purchase_links("article", preparation)
    query = parse_qs(urlparse(result["links"][0]["url"]).query)
    destination = query["destination"][0]

    assert urlparse(destination).netloc == "www.article.com"
    assert parse_qs(urlparse(destination).query)["q"] == ["sofá modular de lino"]
    assert query["subid"] == ["renueva-project-1"]
    assert "comisión" in result["provider_disclosure"]
    assert "seguimiento afiliado activo" in result["guidance"]


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


def test_kroger_public_api_returns_real_store_offer_without_exposing_secret(monkeypatch):
    monkeypatch.delenv("ROXY_HOME_PRICE_FEED_URL", raising=False)
    monkeypatch.delenv("ROXY_HOME_PRICE_FEED_API_KEY", raising=False)
    monkeypatch.setenv("ROXY_HOME_KROGER_CLIENT_ID", "client-id")
    monkeypatch.setenv("ROXY_HOME_KROGER_CLIENT_SECRET", "server-only-kroger-secret")

    class Response:
        def __init__(self, payload):
            import json

            self.payload = json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.payload

    def fake_urlopen(request, timeout):
        assert timeout == 12
        if request.full_url.endswith("/connect/oauth2/token"):
            assert request.headers["Authorization"].startswith("Basic ")
            return Response({"access_token": "short-lived-token"})
        assert request.headers["Authorization"] == "Bearer short-lived-token"
        if "/locations?" in request.full_url:
            return Response({"data": [{"locationId": "01100479", "chain": "Kroger"}]})
        assert "/products?" in request.full_url
        return Response(
            {
                "data": [
                    {
                        "productId": "0001111041700",
                        "description": "Kroger Whole Milk",
                        "brand": "Kroger",
                        "categories": ["Dairy"],
                        "images": [{"sizes": [{"url": "https://www.kroger.com/product/images/small/milk.jpg"}]}],
                        "items": [{"size": "1 gal", "price": {"regular": 3.79}}],
                    }
                ]
            }
        )

    monkeypatch.setattr("roxy_os.home_price_recommendations.urllib.request.urlopen", fake_urlopen)
    offers = fetch_price_offers(
        [{"name": "Leche", "query": "Leche", "quantity": 1, "unit": "galón"}],
        {"postal_code": "33101"},
        config=PriceFeedConfig.from_env(),
    )
    result = recommend_prices(
        [{"name": "Leche", "quantity": 1, "unit": "galón"}],
        offers,
        {"objective": "lowest_price", "organic_preference": "no_preference"},
    )

    assert result["status"] == "READY"
    assert result["recommendations"][0]["retailer_name"] == "Kroger"
    assert result["recommendations"][0]["price"] == 3.79
    assert result["recommendations"][0]["unit_price"] == 0.03
    assert result["recommendations"][0]["comparison_unit"] == "fl oz"
    assert result["recommendations"][0]["image_url"].endswith("milk.jpg")
    assert "server-only-kroger-secret" not in str(result)


def test_kroger_rejects_cheaper_unrelated_catalog_result(monkeypatch):
    monkeypatch.delenv("ROXY_HOME_PRICE_FEED_URL", raising=False)
    monkeypatch.delenv("ROXY_HOME_PRICE_FEED_API_KEY", raising=False)
    monkeypatch.setenv("ROXY_HOME_KROGER_CLIENT_ID", "client-id")
    monkeypatch.setenv("ROXY_HOME_KROGER_CLIENT_SECRET", "secret")

    class Response:
        def __init__(self, payload):
            import json

            self.payload = json.dumps(payload).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return self.payload

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/connect/oauth2/token"):
            return Response({"access_token": "token"})
        if "/locations?" in request.full_url:
            return Response({"data": [{"locationId": "1", "chain": "Kroger"}]})
        return Response({"data": [
            {"productId": "starch", "description": "Corn Starch", "items": [{"size": "14 oz", "price": {"regular": 1.99}}]},
            {"productId": "flour", "description": "Whole Wheat Flour", "items": [{"size": "5 lb", "price": {"regular": 4.49}}]},
        ]})

    monkeypatch.setattr("roxy_os.home_price_recommendations.urllib.request.urlopen", fake_urlopen)
    offers = fetch_price_offers(
        [{"name": "Harina de trigo", "query": "Harina de trigo", "quantity": 1, "unit": "bolsa"}],
        {"postal_code": "33101"},
        config=PriceFeedConfig.from_env(),
    )

    assert [row["product_title"] for row in offers] == ["Whole Wheat Flour"]
    assert offers[0]["unit_price"] == 0.0561
    assert offers[0]["comparison_unit"] == "oz"


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


class _CatalogResponse:
    def __init__(self, payload):
        import json
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def test_ebay_browse_uses_server_credentials_and_returns_real_product_cards(monkeypatch):
    from roxy_os import home_commerce

    monkeypatch.setenv("ROXY_HOME_EBAY_CLIENT_ID", "home-client")
    monkeypatch.setenv("ROXY_HOME_EBAY_CLIENT_SECRET", "home-secret")
    monkeypatch.setenv("ROXY_HOME_EBAY_AFFILIATE_CAMPAIGN_ID", "campaign-1")
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        if "oauth2/token" in request.full_url:
            return _CatalogResponse({"access_token": "token-123", "expires_in": 7200})
        return _CatalogResponse({"itemSummaries": [{
            "title": "Vintage oak side table", "price": {"value": "89.95", "currency": "USD"},
            "condition": "Pre-Owned", "itemWebUrl": "https://www.ebay.com/itm/123",
            "image": {"imageUrl": "https://i.ebayimg.com/images/123.jpg"},
        }]})

    monkeypatch.setattr(home_commerce.urllib.request, "urlopen", fake_urlopen)
    preparation = {"providers": ["ebay"], "items": [{
        "name": "mesa auxiliar de roble", "query": "mesa auxiliar roble", "quantity": 1,
        "unit": "unidad", "category": "HOUSEHOLD", "postal_code": "32801",
    }]}
    result = create_purchase_links("ebay", preparation)

    assert result["mode"] == "product_links"
    assert result["links"][0]["price"] == 89.95
    assert result["links"][0]["image_url"].startswith("https://i.ebayimg.com/")
    assert requests[0].get_header("Authorization").startswith("Basic ")
    assert requests[1].get_header("Authorization") == "Bearer token-123"
    assert "affiliateCampaignId=campaign-1" in requests[1].get_header("X-ebay-c-enduserctx")
    assert "zip%3D32801" in requests[1].get_header("X-ebay-c-enduserctx")


def test_best_buy_products_returns_price_image_availability_and_brand(monkeypatch):
    from roxy_os import home_commerce

    monkeypatch.setenv("ROXY_HOME_BEST_BUY_API_KEY", "best-buy-home-key")

    def fake_urlopen(request, timeout):
        assert request.full_url.startswith("https://api.bestbuy.com/v1/products(search=")
        assert "apiKey=best-buy-home-key" in request.full_url
        return _CatalogResponse({"products": [{
            "name": "Smart floor lamp", "salePrice": 119.99, "regularPrice": 149.99,
            "url": "https://www.bestbuy.com/site/lamp/1.p", "image": "https://pisces.bbystatic.com/image2/lamp.jpg",
            "onlineAvailability": True, "manufacturer": "Example Lighting",
        }]})

    monkeypatch.setattr(home_commerce.urllib.request, "urlopen", fake_urlopen)
    preparation = {"providers": ["best_buy"], "items": [{
        "name": "lámpara inteligente", "query": "smart floor lamp", "quantity": 1,
        "unit": "unidad", "category": "HOUSEHOLD",
    }]}
    result = create_purchase_links("best_buy", preparation)

    assert result["links"][0] == {
        "label": "Smart floor lamp", "shopping_item": "lámpara inteligente", "quantity": 1,
        "unit": "unidad", "category": "HOUSEHOLD", "reason": "Resultado real de Best Buy.",
        "price": 119.99, "regular_price": 149.99, "currency": "USD", "available": True,
        "brand": "Example Lighting", "image_url": "https://pisces.bbystatic.com/image2/lamp.jpg",
        "url": "https://www.bestbuy.com/site/lamp/1.p",
    }


def test_credential_catalogs_are_only_enabled_when_home_keys_exist(monkeypatch):
    for key in ("ROXY_HOME_EBAY_CLIENT_ID", "ROXY_HOME_EBAY_CLIENT_SECRET", "ROXY_HOME_BEST_BUY_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    pending = {row["id"]: row for row in public_providers()}
    assert pending["ebay"]["configured"] is False
    assert pending["best_buy"]["configured"] is False

    monkeypatch.setenv("ROXY_HOME_EBAY_CLIENT_ID", "id")
    monkeypatch.setenv("ROXY_HOME_EBAY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ROXY_HOME_BEST_BUY_API_KEY", "key")
    ready = {row["id"]: row for row in public_providers()}
    assert ready["ebay"]["configured"] is True
    assert ready["best_buy"]["configured"] is True


def test_connected_catalog_failure_keeps_an_honest_official_search_fallback(monkeypatch):
    from roxy_os import home_commerce

    monkeypatch.setenv("ROXY_HOME_BEST_BUY_API_KEY", "best-buy-home-key")

    def unavailable(*_args, **_kwargs):
        raise home_commerce.urllib.error.URLError("offline")

    monkeypatch.setattr(home_commerce.urllib.request, "urlopen", unavailable)
    result = create_purchase_links("best_buy", {
        "providers": ["best_buy"],
        "items": [{"name": "televisor para sala", "query": "televisor sala", "quantity": 1, "unit": "unidad"}],
    })

    assert result["links"][0]["url"].startswith("https://www.bestbuy.com/site/searchpage.jsp?")
    assert result["links"][0].get("price") is None
    assert "no respondió" in result["guidance"]
    assert "sin inventar precios" in result["guidance"]


def test_impact_searches_approved_catalogs_and_creates_confirmed_tracking_link(monkeypatch):
    from roxy_os import home_commerce

    monkeypatch.setenv("ROXY_HOME_IMPACT_ACCOUNT_SID", "IR-home")
    monkeypatch.setenv("ROXY_HOME_IMPACT_AUTH_TOKEN", "impact-secret")
    monkeypatch.setenv("ROXY_HOME_IMPACT_MEDIA_PROPERTY_ID", "property-7")
    assert next(row for row in public_providers() if row["id"] == "impact")["configured"] is True
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        if "/TrackingLinks?" in request.full_url:
            return _CatalogResponse({"TrackingURL": "https://brand.sjv.io/c/123/456/789"})
        return _CatalogResponse({"Items": [{
            "Name": "Oak reading lamp", "CurrentPrice": "79.99", "OriginalPrice": "99.99",
            "Currency": "USD", "StockAvailability": "InStock", "Manufacturer": "Home Brand",
            "CampaignId": "456", "CampaignName": "Home Brand Program",
            "Url": "https://brand.example/lamp", "ImageUrl": "https://brand.example/lamp.jpg",
        }]})

    monkeypatch.setattr(home_commerce.urllib.request, "urlopen", fake_urlopen)
    result = create_purchase_links("impact", {
        "providers": ["impact"], "tracking_id": "private-random-id",
        "items": [{"name": "lámpara de lectura", "query": "oak reading lamp", "quantity": 1, "unit": "unidad"}],
    })

    assert result["links"][0]["url"] == "https://brand.sjv.io/c/123/456/789"
    assert result["links"][0]["affiliate_connected"] is True
    assert result["links"][0]["price"] == 79.99
    assert requests[0].get_header("Authorization").startswith("Basic ")
    tracking_query = parse_qs(urlparse(requests[1].full_url).query)
    assert tracking_query["DeepLink"] == ["https://brand.example/lamp"]
    assert tracking_query["subId1"] == ["private-random-id"]
    assert tracking_query["MediaPartnerPropertyId"] == ["property-7"]


def test_impact_tracking_failure_uses_product_destination_without_claiming_affiliation(monkeypatch):
    from roxy_os import home_commerce

    monkeypatch.setenv("ROXY_HOME_IMPACT_ACCOUNT_SID", "IR-home")
    monkeypatch.setenv("ROXY_HOME_IMPACT_AUTH_TOKEN", "impact-secret")
    calls = 0

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise home_commerce.urllib.error.URLError("tracking unavailable")
        return _CatalogResponse({"Items": [{
            "Name": "Cotton curtain", "CurrentPrice": "45", "CampaignId": "12",
            "Url": "https://brand.example/curtain",
        }]})

    monkeypatch.setattr(home_commerce.urllib.request, "urlopen", fake_urlopen)
    result = create_purchase_links("impact", {
        "providers": ["impact"], "tracking_id": "anonymous-id",
        "items": [{"name": "cortina", "query": "cotton curtain"}],
    })

    assert result["links"][0]["url"] == "https://brand.example/curtain"
    assert result["links"][0]["affiliate_connected"] is False


def test_dataforseo_charges_once_then_reuses_task_id_for_results(monkeypatch):
    from roxy_os import home_commerce
    monkeypatch.setenv("ROXY_HOME_DATAFORSEO_LOGIN", "home-login")
    monkeypatch.setenv("ROXY_HOME_DATAFORSEO_PASSWORD", "home-password")
    calls = []
    def fake_urlopen(request, timeout):
        calls.append(request)
        if request.get_method() == "POST":
            return _CatalogResponse({"tasks": [{"id": "06181608-2806-0179-0000-aff47b17cd54", "status_code": 20100}]})
        return _CatalogResponse({"tasks": [{"result": [{"keyword": "floor lamp", "check_url": "https://google.com/search?q=floor+lamp", "items": [{"items": [{"title": "Modern Floor Lamp", "seller": "Lamp Shop", "price": 59.99, "currency": "USD", "product_images": ["https://images.example/lamp.jpg"], "shopping_url": "https://google.com/search?q=modern+lamp"}]}]}]}]})
    monkeypatch.setattr(home_commerce.urllib.request, "urlopen", fake_urlopen)
    preparation = {"providers": ["dataforseo"], "items": [{"name": "lámpara", "query": "floor lamp"}]}
    queued = create_purchase_links("dataforseo", preparation)
    ready = create_purchase_links("dataforseo", preparation, task_ids=queued["catalog_task_ids"])
    assert queued["catalog_status"] == "processing"
    assert ready["catalog_status"] == "ready"
    assert ready["links"][0]["price"] == 59.99
    assert [request.get_method() for request in calls] == ["POST", "GET"]
