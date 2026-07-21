from pathlib import Path

import streamlit_app
from streamlit_app import (
    brand_logo_html,
    roxy_avatar_html,
    roxy_hologram_avatar_html,
    roxy_welcome_card_html,
)


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


def test_roxy_avatar_html_embeds_avatar_asset():
    html = roxy_avatar_html("speaking", "mini")

    assert "roxy-avatar" in html
    assert "roxy-avatar-speaking" in html
    assert "data:image/jpeg;base64," in html
    assert "Roxy AI" in html


def test_roxy_hologram_avatar_embeds_human_face_rig():
    html = roxy_hologram_avatar_html("speaking", "Roxy Trading AI")

    assert "roxy-human-rig" in html
    assert "roxy-eye-lid-left" in html
    assert "roxy-eye-lid-right" in html
    assert "roxy-mouth-rig" in html
    assert "roxy-cheek-left" in html
    assert html.count("data:image/jpeg;base64,") == 1
    assert "roxy-neck-head" not in html


def test_roxy_hologram_face_layers_are_not_disabled():
    styles = streamlit_app.roxy_application_style_markup(include_academy_auth=True)

    assert ".roxy-gaze,.roxy-mouth,.roxy-lip,.roxy-blink,.roxy-eye{display:none" not in styles
    assert "@keyframes roxyHumanBlink" in styles
    assert "@keyframes roxyHumanTalk" in styles


def test_roxy_avatar_html_falls_back_to_svg_when_asset_missing(monkeypatch):
    monkeypatch.setitem(streamlit_app.ROXY_AVATAR_VARIANT_PATHS, "mini", Path("/tmp/roxy-missing-avatar.jpg"))

    html = roxy_avatar_html("ready", "mini")

    assert "<svg" in html
    assert "Roxy logo" in html


def test_roxy_welcome_card_html_embeds_card_variant():
    html = roxy_welcome_card_html()

    assert "roxy-welcome-card" in html
    assert "data:image/jpeg;base64," in html
    assert "Roxy IA activa" in html
