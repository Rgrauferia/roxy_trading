import json
from pathlib import Path

import pandas as pd

from roxy_ai import extract_opportunities
from roxy_knowledge_brain import RoxyKnowledgeBrain


def write_fragments(root: Path) -> None:
    doc = root / "ema-risk"
    doc.mkdir(parents=True)
    (doc / "fragments.json").write_text(
        json.dumps(
            [
                {
                    "id": "ema-risk-0001",
                    "title": "EMA risk management notes",
                    "category": "estrategias-internas",
                    "source": "manual",
                    "processedAt": "2026-07-01T00:00:00Z",
                    "content": "EMA 9 and EMA 21 pullback setups need entry, stop loss, target, volume confirmation and risk reward before trading.",
                },
                {
                    "id": "bollinger-0001",
                    "title": "Bollinger confirmation",
                    "category": "indicadores",
                    "source": "manual",
                    "processedAt": "2026-07-01T00:00:00Z",
                    "content": "Bollinger Bands expand with volatility. Confirm breakout with volume and momentum before entering.",
                },
            ]
        ),
        encoding="utf-8",
    )


def test_knowledge_brain_searches_processed_fragments(tmp_path):
    write_fragments(tmp_path)
    brain = RoxyKnowledgeBrain(tmp_path).load()

    results = brain.search("AAPL EMA 9 21 pullback entry stop target volume", limit=2)

    assert results
    assert results[0]["title"] == "EMA risk management notes"
    assert results[0]["category"] == "estrategias-internas"


def test_knowledge_enrichment_preserves_original_trade_fields(tmp_path):
    write_fragments(tmp_path)
    brain = RoxyKnowledgeBrain(tmp_path).load()
    original = {
        "symbol": "AAPL",
        "market": "stock",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_2PCT",
        "entry": 289.25,
        "stop": 286.75,
        "recommended_target_price": 295.0,
        "risk_pct": 0.0086,
        "ai_score": 88,
        "strategy_family": "EMA 9/21 Pullback",
        "relative_volume": 1.4,
    }

    enriched = brain.enrich_opportunity(original)

    for key in ("signal", "trade_decision", "entry", "stop", "recommended_target_price", "risk_pct", "ai_score"):
        assert enriched[key] == original[key]
    assert enriched["knowledge_context_status"] == "READY"
    assert enriched["knowledge_enrichment"]["mode"] == "enrich_only_preserve_strategy"
    assert enriched["knowledge_enrichment"]["source_fragments"]


def test_knowledge_enrichment_flags_missing_operational_fields(tmp_path):
    write_fragments(tmp_path)
    brain = RoxyKnowledgeBrain(tmp_path).load()

    enriched = brain.enrich_opportunity({"symbol": "MSFT", "signal": "WATCH", "ai_score": 72})

    notes = " ".join(enriched["knowledge_enrichment"]["risk_notes"])
    assert "Falta entrada" in notes
    assert "Falta stop" in notes
    assert "Falta target" in notes


def test_extract_opportunities_adds_knowledge_without_breaking_strategy_fields():
    frame = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "stock",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "entry": 289.25,
                "stop": 286.75,
                "recommended_target_price": 295.0,
                "recommended_target_pct": 0.02,
                "risk_pct": 0.0086,
                "confluence_score": 88,
                "score": 88,
                "trend_score": 80,
                "relative_volume": 1.4,
                "trigger_setup": "EMA 9/21 Pullback",
                "trend_setup": "1h tendencia alcista",
            }
        ]
    )

    rows = extract_opportunities(frame, limit=1)

    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["signal"] == "BUY"
    assert rows[0]["entry"] == 289.25
    assert "knowledge_enrichment" in rows[0]
