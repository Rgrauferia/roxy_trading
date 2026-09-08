"""Voice/search must resolve the same reviewed edition as the visible cookbook."""
from roxy_os.home_recipe_fallback import find_local_recipe, exact_local_recipe


def test_recovered_drink_does_not_resolve_to_installed_generic_duplicate():
    wanted = exact_local_recipe("Piña colada sin alcohol")
    found = find_local_recipe("Dame una piña colada sin alcohol", {})
    assert found["editorial_status"] == "reviewed_local"
    assert found["ingredients"] == wanted["ingredients"]
    assert found["steps"] == wanted["steps"]
    assert len(found["ingredients"]) == 4
    assert any(row["name"] == "Leche de coco" for row in found["ingredients"])


def test_specific_unavailable_request_is_not_substituted_by_chicken():
    assert find_local_recipe("Quiero preparar injera etíope", {}) is None
