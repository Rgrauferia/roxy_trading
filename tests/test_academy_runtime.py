from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import streamlit_app as app


def test_academy_progress_concurrent_users_are_preserved(tmp_path, monkeypatch) -> None:
    path = tmp_path / "academy.json"
    monkeypatch.setattr(app, "ROXY_ACADEMY_PROGRESS_PATH", path)
    monkeypatch.setattr(app, "roxy_load_academy_progress_store", lambda: {})

    def save(index: int) -> None:
        state = app.roxy_academy_default_progress()
        state["xp"] = 100 + index
        app.roxy_save_academy_progress(f"user-{index:02d}", state)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(save, range(16)))

    stored = json.loads(path.read_text())
    assert len(stored) == 16
    assert {stored[f"user-{index:02d}"]["xp"] for index in range(16)} == set(range(100, 116))
    assert path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / ".academy.json.lock").stat().st_mode & 0o777 == 0o600


def test_academy_origin_lesson_contract_is_complete_and_unique() -> None:
    lessons = app.ROXY_ACADEMY_LEVEL_1_LESSONS
    required = {
        "id",
        "title",
        "short",
        "icon",
        "character",
        "explanation",
        "study",
        "mission",
        "question",
        "options",
        "answer",
        "feedback",
    }
    assert len(lessons) >= 20
    assert len({item["id"] for item in lessons}) == len(lessons)
    assert all(required <= set(item) for item in lessons)
    assert all(len(item["options"]) >= 4 for item in lessons)
    assert lessons[-1]["id"] == "examen-nivel-1"


def test_academy_module_renders_without_undefined_runtime_contracts(monkeypatch) -> None:
    rendered: list[str] = []
    fake_streamlit = SimpleNamespace(
        session_state={"user": "diagnostic_probe"},
        query_params={},
        markdown=lambda markup, **_kwargs: rendered.append(markup),
    )
    fallback_context = {
        "planet": "origen",
        "role": "Fundamentos",
        "points": ["Punto verificable"],
        "practice": ["Practica verificable"],
        "sources": [],
    }
    monkeypatch.setattr(app, "st", fake_streamlit)
    monkeypatch.setattr(app, "roxy_load_academy_progress_store", lambda: {})
    monkeypatch.setattr(app, "academy_asset_img_html", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        app,
        "roxy_academy_live_market_example",
        lambda symbol="AAPL": {"symbol": symbol, "status": "unavailable", "as_of": "-"},
    )
    monkeypatch.setattr(app, "planet_curriculum_summary", lambda _planet: fallback_context)
    monkeypatch.setattr(
        app,
        "enrich_academy_lesson",
        lambda _planet, lesson: {**lesson, "knowledge_context": fallback_context},
    )

    app.render_roxy_academy_module()

    assert len(rendered) == 1
    assert "Roxy Academy" in rendered[0]
    assert "Planeta Origen" in rendered[0]


def test_academy_market_example_uses_bounded_delayed_download(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeYFinance:
        @staticmethod
        def download(_symbol: str, **kwargs):
            calls.append(kwargs)
            return None

    monkeypatch.setattr(app, "yf", FakeYFinance())
    function = getattr(app.roxy_academy_live_market_example, "__wrapped__", app.roxy_academy_live_market_example)

    result = function("AAPL")

    assert result["status"] == "unavailable"
    assert calls[0]["timeout"] == 4
    assert calls[0]["interval"] == "1d"
    assert calls[0]["threads"] is False
