import json

from tools.roxy_stock_stream_bridge import normalize_stock_symbols, sse_event


def test_normalize_stock_symbols_limits_and_sanitizes_input():
    symbols = normalize_stock_symbols(" aapl, MSFT; nvda!, TSLA, AAPL ")

    assert symbols == ["AAPL", "MSFT", "NVDA", "TSLA"]
    assert len(normalize_stock_symbols(",".join(f"SYM{i}" for i in range(40)))) == 24


def test_sse_event_contains_named_event_and_json_payload():
    packed = sse_event("quote", {"symbol": "AAPL", "price": 100.25})

    assert packed.startswith("event: quote\n")
    data_line = [line for line in packed.splitlines() if line.startswith("data: ")][0]
    assert json.loads(data_line.replace("data: ", "")) == {"symbol": "AAPL", "price": 100.25}
