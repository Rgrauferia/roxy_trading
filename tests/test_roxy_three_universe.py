from pathlib import Path

import streamlit_app


SOURCE = Path("streamlit_app.py").read_text(encoding="utf-8")
THREE_RUNTIME_TEMPLATE = Path("assets/runtime/roxy_three_universe_runtime.js.html").read_text(encoding="utf-8")
THREE_RUNTIME_SOURCE = SOURCE + THREE_RUNTIME_TEMPLATE


def test_three_universe_runtime_is_registered_without_module_scripts():
    assert "def render_roxy_three_universe_runtime" in SOURCE
    assert Path("assets/vendor/three.r128.min.js").exists()
    assert "three.r128.min.js" in SOURCE
    assert "three.min.js" in THREE_RUNTIME_SOURCE
    assert 'type="module"' not in THREE_RUNTIME_SOURCE


def test_three_universe_runtime_mounts_existing_and_future_universe_layers():
    runtime = SOURCE[SOURCE.index("def render_roxy_three_universe_runtime") :] + THREE_RUNTIME_TEMPLATE

    assert "MutationObserver" in runtime
    assert ".roxy-universe:not([data-roxy-three-mounted])" in runtime
    assert "roxy-three-canvas" in runtime
    assert "roxy-three-fallback-hidden" in runtime


def test_three_universe_runtime_escapes_vendor_script_breakouts():
    markup = streamlit_app.roxy_three_universe_runtime_markup(
        "window.THREE={};</script><script>alert('three')&x=1\u2028"
    )

    assert "__ROXY_THREE_INLINE_SOURCE__" not in markup
    assert "</script><script>alert('three')" not in markup
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert('three')\\u0026x=1\\u2028" in markup
    assert "MutationObserver" in markup


def test_three_universe_runtime_is_not_loaded_on_operational_routes():
    main = SOURCE[SOURCE.index("def main()") :]
    academy_gate = main.index('== "academy":')
    runtime_call = main.index("render_roxy_three_universe_runtime()")
    focused_app = main.index("render_with_diagnostic_profile(")

    assert academy_gate < runtime_call < focused_app
    assert "render_roxy_three_universe_runtime()" not in main[:academy_gate]
