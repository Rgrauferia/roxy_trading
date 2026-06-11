from streamlit_app import company_research_hub_rows


def test_company_research_hub_stock_links_use_selected_symbol():
    rows = company_research_hub_rows("WMT", "stock")

    assert rows["label"].tolist() == ["Finviz", "TradingView", "Yahoo", "SEC", "Nasdaq"]
    assert rows.iloc[0]["url"] == "https://finviz.com/quote.ashx?t=WMT"
    assert "finance.yahoo.com/quote/WMT" in rows.iloc[2]["url"]
    assert rows.iloc[3]["kind"] == "Filings"


def test_company_research_hub_crypto_uses_pair_without_slash_for_chart_links():
    rows = company_research_hub_rows("BTC/USD", "crypto")

    assert rows["label"].tolist() == ["TradingView", "Yahoo", "CoinMarketCap", "Alpaca"]
    assert "BTCUSD" in rows.iloc[0]["url"]
    assert rows.iloc[-1]["url"] == "https://alpaca.markets/docs/"


def test_company_research_hub_sanitizes_symbol_and_handles_empty_input():
    rows = company_research_hub_rows("WMT<script>", "stock")
    empty = company_research_hub_rows("", "stock")

    assert rows.iloc[0]["url"].endswith("WMTSCRIPT")
    assert empty.empty
