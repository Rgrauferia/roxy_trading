from market_newsletter import (
    analyze_newsletter_text,
    append_newsletter,
    build_newsletter_record,
    newsletter_context,
    read_newsletters,
)


def test_analyze_newsletter_maps_finhabits_topics_to_watchlist():
    analysis = analyze_newsletter_text(
        "Esta semana hubo noticias sobre inflacion, la FED, SpaceX hizo historia y Bitcoin subio."
    )

    assert analysis["risk_level"] == "HIGH"
    assert "SPY" in analysis["watchlist_symbols"]
    assert "BTC/USD" in analysis["watchlist_symbols"]
    assert "TSLA" in analysis["watchlist_symbols"]
    assert any(item["theme"] == "rates_inflation" for item in analysis["themes"])


def test_newsletter_context_reads_latest_records(tmp_path):
    path = tmp_path / "weekly_newsletters.jsonl"
    record = build_newsletter_record(
        source="Finhabits",
        subject="Resumen de la Semana",
        received_at="2026-06-13T11:04:00-04:00",
        body="IA, Nvidia, consumo y tasas de interes afectan el bolsillo.",
    )

    append_newsletter(record, path=path)
    rows = read_newsletters(path)
    context = newsletter_context(path)

    assert len(rows) == 1
    assert context["configured"] is True
    assert context["label"] == "Newsletter semanal"
    assert "NVDA" in context["watchlist_symbols"]
    assert context["market_news"][0]["source"] == "Finhabits"
    assert context["usage_rule"].startswith("Contexto solamente")
