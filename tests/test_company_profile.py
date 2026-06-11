from streamlit_app import compact_large_number, company_profile_summary


def test_compact_large_number_formats_market_cap_scale():
    assert compact_large_number(2_450_000_000_000) == "2.45T"
    assert compact_large_number(325_000_000_000) == "325.00B"
    assert compact_large_number(12_500_000) == "12.50M"
    assert compact_large_number(None) == "-"


def test_company_profile_summary_normalizes_key_fields():
    summary = company_profile_summary(
        {
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "United States",
            "marketCap": 3_000_000_000_000,
            "currentPrice": 200.12,
            "trailingPE": 31.4,
            "beta": 1.18,
            "fiftyTwoWeekLow": 164.08,
            "fiftyTwoWeekHigh": 237.49,
            "website": "https://www.apple.com",
            "longBusinessSummary": "Apple designs products.",
        }
    )

    assert summary["name"] == "Apple Inc."
    assert summary["sector"] == "Technology"
    assert summary["industry"] == "Consumer Electronics"
    assert summary["market_cap"] == "3.00T"
    assert summary["price"] == "200.12"
    assert summary["pe"] == "31.40"
    assert summary["beta"] == "1.18"
    assert summary["range_52w"] == "164.08 / 237.49"
