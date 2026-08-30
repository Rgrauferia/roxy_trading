from pathlib import Path

import requests

from roxy_os.home_product_intelligence import (
    HomeProductIntelligence,
    ProductIntelligenceConfig,
    normalize_barcode,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self.payload


def service(tmp_path: Path, responder, *, usda_key="usda-test-key"):
    config = ProductIntelligenceConfig(
        cache_path=tmp_path / "products.sqlite",
        user_agent="RoxyHomeTest/1.0",
        usda_api_key=usda_key,
        timeout_seconds=2,
        cache_hours=24,
    )
    return HomeProductIntelligence(config, request=responder)


def test_normalize_barcode_accepts_spacing_and_rejects_short_values():
    assert normalize_barcode("3017 6204 22003") == "3017620422003"
    try:
        normalize_barcode("123")
    except ValueError as error:
        assert "8 y 14" in str(error)
    else:
        raise AssertionError("A short barcode must be rejected")


def test_lookup_combines_product_nutrition_and_recall_sources(tmp_path):
    calls = []

    def responder(method, url, **kwargs):
        calls.append((method, url))
        if "openfoodfacts" in url:
            return FakeResponse({"status": 1, "product": {
                "product_name_es": "Crema de avellanas",
                "brands": "Marca prueba",
                "quantity": "350 g",
                "image_front_url": "https://images.openfoodfacts.org/product.jpg",
                "nutriscore_grade": "d",
                "nova_group": 4,
                "nutriments": {"energy-kcal_100g": 530, "proteins_100g": 6.3},
            }})
        if "nal.usda.gov" in url:
            return FakeResponse({"foods": [{
                "fdcId": 123,
                "description": "CREMA DE AVELLANAS",
                "brandOwner": "Marca prueba",
                "servingSize": 30,
                "servingSizeUnit": "g",
                "foodNutrients": [{"nutrientName": "Protein", "value": 6.3, "unitName": "G"}],
            }]})
        return FakeResponse([{
            "RecallID": "99",
            "Title": "Crema de avellanas retirada",
            "Description": "Posible alérgeno no declarado",
            "RecallDate": "2026-08-01",
            "URL": "https://www.cpsc.gov/Recalls/99",
        }])

    engine = service(tmp_path, responder)
    result = engine.lookup(barcode="3017620422003")

    assert result["status"] == "FOUND"
    assert result["product"]["name"] == "Crema de avellanas"
    assert result["product"]["nutrition_per_100g"]["Energía"]["value"] == 530
    assert result["nutrition_reference"]["source"]["id"] == "usda"
    assert result["recall_summary"]["status"] == "POTENTIAL_MATCHES"
    assert {source["id"] for source in result["sources"]} == {"open_food_facts", "usda", "cpsc"}
    assert len(calls) == 3

    cached = engine.lookup(barcode="3017620422003")
    assert cached["cache"]["hit"] is True
    assert len(calls) == 3


def test_lookup_keeps_partial_verified_result_when_optional_source_fails(tmp_path):
    def responder(method, url, **kwargs):
        if "openfoodfacts" in url:
            return FakeResponse({"status": 1, "product": {"product_name": "Milk", "brands": "Test"}})
        return FakeResponse({}, status=503)

    result = service(tmp_path, responder).lookup(barcode="012345678905")
    assert result["status"] == "FOUND"
    assert result["product"]["name"] == "Milk"
    assert result["source_errors"]
    assert "no garantiza" in result["recall_summary"]["message"]


def test_usda_is_explicitly_disabled_without_server_key(tmp_path):
    calls = []

    def responder(method, url, **kwargs):
        calls.append(url)
        return FakeResponse([])

    engine = service(tmp_path, responder, usda_key="")
    assert engine.status()["usda"]["enabled"] is False
    result = engine.lookup(query="arroz integral")
    assert result["status"] == "NO_MATCH"
    assert result["capabilities"] == {"barcode_lookup": True, "name_lookup": False}
    assert not any("nal.usda.gov" in url for url in calls)
