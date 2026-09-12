"""Synthetic provider data only: no mirrored recipe text or live calls."""
from concurrent.futures import ThreadPoolExecutor
import json

import pytest
import requests

from roxy_os import home_myplate_recipes as recipes


def card(slug="fixture-dish"):
    return {"slug": slug, "name": "Synthetic fixture dish", "description": "Fixture only.",
            "category": "Main dish", "image_url": f"https://storage.googleapis.com/peppermint-cdn/myplate.food-recipe-images/{slug}.jpg",
            "recipe_url": f"https://myplate.food/recipes/{slug}",
            "api_url": f"https://myplate.food/api/v1/recipes/{slug}",
            "locales": {"es": "https://myplate.food/es/recipes/plato-de-prueba"}}


def detail(slug="fixture-dish"):
    return {**card(slug), "category": None,
            "ingredients": [{"text": "1 cup synthetic ingredient", "note": "fixture note"},
                            {"text": "2 units another fixture", "note": None}],
            "directions": "First original paragraph.\n\nSecond original paragraph: preserve 1/2 exactly.",
            "yield": "2–3 portions", "serving_size": "1 piece", "notes": "Source note.\nUnchanged.",
            "contributor": "Synthetic test contributor", "source": "Synthetic test source",
            "source_url": f"https://www.myplate.gov/recipes/{slug}",
            "canonical_url": f"https://myplate.food/recipes/{slug}"}


def search_payload(rows=None, total=None):
    rows = [card()] if rows is None else rows
    return {"results": rows, "count": len(rows), "total": len(rows) if total is None else total,
            "source": "Synthetic test source", "canonical_url": "https://myplate.food/recipes"}


class Response:
    def __init__(self, payload=None, *, status=200, headers=None, body=None):
        self.status_code = status
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.body = body if body is not None else json.dumps(payload).encode()
        self.closed = False

    def iter_content(self, chunk_size):
        yield self.body

    def close(self):
        self.closed = True


def provider(payload=None, *, response=None, clock=None):
    calls = []
    response = response or Response(payload)
    clock = clock or (lambda: 1.0)

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    return recipes.MyPlateRecipeProvider(request_get=get, limiter=recipes._RateLimiter(clock), clock=clock), calls, response


def test_search_normalized_under_demand_and_no_profile_parameters():
    p, calls, response = provider(search_payload(total=1072))
    result = p.search(q=" pasta ", category="Main dish", offset=0, limit=24)
    assert result["total"] == 1072
    assert result["next_offset"] == 1
    assert result["offset"] == 0 and result["limit"] == 24
    assert result["recipes"][0]["title"] == "Synthetic fixture dish"
    assert result["recipes"][0]["translation_urls"]["es"].startswith("https://myplate.food/es/")
    assert result["audience"] == "human" and result["storage"] == "transient_only"
    assert result["live"] is True
    assert calls == [(recipes.API_BASE + "/recipes", {
        "params": {"q": "pasta", "category": "Main dish", "limit": 24, "offset": 0},
        "stream": True, "timeout": (3, 5), "allow_redirects": False,
        "headers": {"Accept": "application/json", "User-Agent": "RoxyHome/recipe-reader"}})]
    assert response.closed


def test_source_text_quantities_and_notes_not_rewritten_or_split():
    original = detail()
    p, calls, response = provider(original)
    result = p.detail("fixture-dish")["recipe"]
    for field in ("ingredients", "directions", "yield", "serving_size", "notes", "contributor", "source"):
        assert result[field] == original[field]
    assert result["language"] == "en" and result["category"] == ""
    assert "steps" not in result and "nutrition" not in result
    assert result["can_cook"] is False and result["can_add_to_shopping"] is False
    assert result["source_url"] == original["recipe_url"]
    assert result["original_source_url"] == original["source_url"]
    assert len(calls) == 1 and response.closed


@pytest.mark.parametrize("category", ["Main dish", "Dessert", "Beverage", "Salad", "Soup",
                                      "Breakfast", "Bread", "Side dish"])
def test_native_categories_are_explicit_filters_not_inferred_text_searches(category):
    row = {**card(), "category": category}
    p, calls, response = provider(search_payload([row]))
    result = p.search(category=category, offset=0, limit=24)
    assert calls[0][1]["params"] == {"category": category, "limit": 24, "offset": 0}
    assert len(calls) == 1 and response.closed
    assert result["recipes"][0]["category"] == category
    assert result["recipes"][0]["can_cook"] is False
    assert result["recipes"][0]["can_add_to_shopping"] is False
    assert result["category_options"] == ["Main dish", "Dessert", "Beverage", "Salad", "Soup",
                                           "Breakfast", "Bread", "Side dish"]


@pytest.mark.parametrize("kwargs", [{"q": "x" * 121}, {"q": "a\nb"}, {"q": None},
                                     {"category": "Snake"}, {"category": "pasta"},
                                     {"category": "Snack"}, {"category": "Desayunos"},
                                     {"category": "side dish"}, {"offset": -1},
                                     {"offset": True}, {"offset": 100001}, {"limit": 0},
                                     {"limit": 25}, {"limit": True}, {"limit": 1.0}])
def test_invalid_search_parameters_never_consume_network(kwargs):
    p, calls, _ = provider(search_payload())
    with pytest.raises(recipes.MyPlateRecipeError) as caught:
        p.search(**kwargs)
    assert caught.value.status_code == 400 and calls == []


@pytest.mark.parametrize("slug", ["../x", "https://evil.example/path", "x?q=1", "x#one", "%2F", "X", "x/y", "x--y", "x\n", "x" * 161, None])
def test_invalid_slug_never_escapes_fixed_origin(slug):
    p, calls, _ = provider(detail())
    with pytest.raises(recipes.MyPlateRecipeError):
        p.detail(slug)
    assert calls == []


@pytest.mark.parametrize("field,value", [
    ("recipe_url", "https://evil.example/recipes/fixture-dish"),
    ("recipe_url", "https://myplate.food@evil.example/recipes/fixture-dish"),
    ("recipe_url", "https://myplate.food:444/recipes/fixture-dish"),
    ("recipe_url", "https://myplate.food/recipes/wrong"),
    ("recipe_url", "https://myplate.food/recipes/fixture-dish?token=secret"),
    ("image_url", "https://storage.googleapis.com/another-bucket/fixture-dish.jpg"),
    ("image_url", "https://myplate.food.example/fixture-dish.jpg"),
    ("image_url", "http://storage.googleapis.com/peppermint-cdn/myplate.food-recipe-images/fixture-dish.jpg"),
    ("image_url", "https://storage.googleapis.com/peppermint-cdn/myplate.food-recipe-images/../x.jpg"),
    ("api_url", "https://myplate.food/api/v1/calculate/bmi"),
    ("locales", {"es": "https://evil.example/es/recipes/fixture"}),
    ("locales", {"es": "https://myplate.food/es/recipes/%2e%2e"}),
    ("locales", {"xx": "https://myplate.food/xx/recipes/fixture"}),
])
def test_provider_urls_fail_closed(field, value):
    raw = card()
    raw[field] = value
    p, _, _ = provider(search_payload([raw]))
    with pytest.raises(recipes.MyPlateRecipeError) as caught:
        p.search()
    assert caught.value.code == "invalid_content"


@pytest.mark.parametrize("field,value", [("name", ""), ("slug", "another-dish"), ("directions", " "),
    ("directions", "a" * 80001), ("directions", ["Not a string"]), ("yield", None),
    ("ingredients", []), ("ingredients", [{"text": "", "note": None}]),
    ("ingredients", [{"text": "1 cup item", "unit": "cup"}]),
    ("ingredients", [{"text": "1 cup item", "note": {}}]), ("notes", []),
    ("source", ""), ("original_source_url", None)])
def test_invalid_or_incomplete_details_not_promoted(field, value):
    # The last case exercises the actual upstream source_url field.
    raw = detail()
    if field == "original_source_url":
        raw["source_url"] = "https://evil.example/recipe"
    else:
        raw[field] = value
    p, _, _ = provider(raw)
    with pytest.raises(recipes.MyPlateRecipeError) as caught:
        p.detail("fixture-dish")
    assert caught.value.status_code == 422


@pytest.mark.parametrize("change", [
    {"total": True}, {"total": -1}, {"total": 100001}, {"count": False}, {"count": 2},
    {"results": {}}, {"total": 0}, {"results": [], "count": 0, "total": 4},
    {"results": [card(), card()], "count": 2, "total": 2},
])
def test_invalid_pagination_not_silently_truncated(change):
    raw = search_payload()
    raw.update(change)
    p, _, _ = provider(raw)
    with pytest.raises(recipes.MyPlateRecipeError):
        p.search()


def test_empty_and_last_page_have_no_fabricated_next_page():
    p, _, _ = provider(search_payload([], 0))
    assert p.search()["next_offset"] is None
    p, _, _ = provider(search_payload(total=25))
    result = p.search(offset=24)
    assert result["next_offset"] is None and len(result["recipes"]) == 1


@pytest.mark.parametrize("status,expected", [(301, 503), (302, 503), (401, 503), (403, 503), (404, 404), (500, 503), (502, 503)])
def test_statuses_return_safe_errors_without_retry(status, expected):
    p, calls, response = provider(response=Response({"secret": "must not escape"}, status=status))
    with pytest.raises(recipes.MyPlateRecipeError) as caught:
        p.search()
    assert caught.value.status_code == expected
    assert "secret" not in str(caught.value)
    assert len(calls) == 1 and response.closed


def test_upstream_retry_after_blocks_all_subsequent_calls_without_retry():
    now = [1.0]
    p, calls, response = provider(response=Response({}, status=429, headers={"Retry-After": "180"}), clock=lambda: now[0])
    with pytest.raises(recipes.MyPlateRecipeError) as caught:
        p.search()
    assert caught.value.retry_after == 180
    now[0] += 10
    with pytest.raises(recipes.MyPlateRecipeError) as second:
        p.detail("fixture-dish")
    assert second.value.retry_after == 170 and len(calls) == 1
    assert response.closed


def test_twenty_requests_per_minute_and_rolling_expiry():
    now = [1.0]
    p, calls, _ = provider(search_payload(), clock=lambda: now[0])
    for _ in range(20):
        p.search()
    with pytest.raises(recipes.MyPlateRecipeError) as caught:
        p.search()
    assert caught.value.status_code == 429 and caught.value.retry_after == 60
    assert len(calls) == 20
    now[0] += 60
    p.search()
    assert len(calls) == 21


def test_hundred_detail_attempts_daily_but_search_stays_available():
    now = [1.0]
    limiter = recipes._RateLimiter(lambda: now[0])
    for _ in range(100):
        limiter.reserve(detail=True)
        now[0] += 61
    with pytest.raises(recipes.MyPlateRecipeError) as caught:
        limiter.reserve(detail=True)
    assert caught.value.retry_after == 86400 - 6100
    limiter.reserve(detail=False)
    now[0] = 86401.0
    limiter.reserve(detail=True)


def test_rate_reservations_thread_safe():
    limiter = recipes._RateLimiter(lambda: 1.0)
    def reserve(_):
        try:
            limiter.reserve(detail=True)
            return True
        except recipes.MyPlateRecipeError:
            return False
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(reserve, range(40))) == 20


@pytest.mark.parametrize("body", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'[]', b'\xff', b'not json'])
def test_strict_json_rejects_malformed_and_duplicate_keys(body):
    p, _, response = provider(response=Response(body=body))
    with pytest.raises(recipes.MyPlateRecipeError) as caught:
        p.search()
    assert caught.value.status_code == 422 and response.closed


@pytest.mark.parametrize("headers,body", [({"Content-Type": "text/html"}, b'{}'),
    ({"Content-Length": "-1"}, b'{}'), ({"Content-Length": "wat"}, b'{}'),
    ({"Content-Length": str(recipes.MAX_RESPONSE_BYTES + 1)}, b'{}'),
    ({}, b' ' * (recipes.MAX_RESPONSE_BYTES + 1))])
def test_response_size_and_type_boundaries(headers, body):
    p, _, response = provider(response=Response(headers=headers, body=body))
    with pytest.raises(recipes.MyPlateRecipeError):
        p.search()
    assert response.closed


@pytest.mark.parametrize("error,code", [(requests.Timeout("sensitive upstream URL"), "timeout"),
    (requests.ConnectionError("sensitive upstream URL"), "unavailable"), (OSError("sensitive path"), "unavailable")])
def test_transport_errors_never_echo_provider_details(error, code):
    def fail(*args, **kwargs):
        raise error
    p = recipes.MyPlateRecipeProvider(request_get=fail, limiter=recipes._RateLimiter())
    with pytest.raises(recipes.MyPlateRecipeError) as caught:
        p.search()
    assert caught.value.code == code
    assert "sensitive" not in str(caught.value)


def test_body_deadline():
    times = iter([0.0, 11.0])
    p, _, response = provider(search_payload())
    p._clock = lambda: next(times)
    with pytest.raises(recipes.MyPlateRecipeError) as caught:
        p.search()
    assert caught.value.code == "timeout" and response.closed


def test_public_wrappers_use_singleton(monkeypatch):
    p, calls, _ = provider(search_payload())
    monkeypatch.setattr(recipes, "_PROVIDER", p)
    assert recipes.search_recipes(q="pasta", limit=1)["total"] == 1
    monkeypatch.setattr(p, "detail", lambda slug: {"fixture": slug})
    assert recipes.get_recipe("fixture-dish") == {"fixture": "fixture-dish"}
    assert len(calls) == 1


@pytest.mark.parametrize("value,expected", [(None, 60), ("junk", 60), ("0", 1), ("42", 42), ("9999999999", 86400)])
def test_retry_after_parsing_is_bounded(value, expected):
    assert recipes._retry_after(value) == expected
