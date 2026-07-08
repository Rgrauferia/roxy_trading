from pathlib import Path


SOURCE = Path("streamlit_app.py").read_text(encoding="utf-8")


def test_three_universe_runtime_is_registered_without_module_scripts():
    assert "def render_roxy_three_universe_runtime" in SOURCE
    assert Path("assets/vendor/three.r128.min.js").exists()
    assert "three.r128.min.js" in SOURCE
    assert "three.min.js" in SOURCE
    assert 'type="module"' not in SOURCE[SOURCE.index("def render_roxy_three_universe_runtime") :]


def test_three_universe_runtime_mounts_existing_and_future_universe_layers():
    runtime = SOURCE[SOURCE.index("def render_roxy_three_universe_runtime") :]

    assert "MutationObserver" in runtime
    assert ".roxy-universe:not([data-roxy-three-mounted])" in runtime
    assert "roxy-three-canvas" in runtime
    assert "roxy-three-fallback-hidden" in runtime
