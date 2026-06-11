from pathlib import Path

import streamlit_app
from streamlit_app import brand_logo_html


def test_brand_logo_html_embeds_grau_service_logo_asset():
    html = brand_logo_html()

    assert "brand-logo-img" in html
    assert "data:image/png;base64," in html
    assert "Grau Service LLC logo" in html


def test_brand_logo_html_falls_back_to_svg_when_asset_missing(monkeypatch):
    monkeypatch.setattr(streamlit_app, "BRAND_LOGO_PATH", Path("/tmp/roxy-missing-logo.png"))

    html = brand_logo_html()

    assert "<svg" in html
    assert "Roxy logo" in html
