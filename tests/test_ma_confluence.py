import subprocess
import sys

import pandas as pd

from ma_confluence import build_confluence, build_confluence_summary, render_confluence_report


def _row(tf, signal, raw_signal, setup, score, eligible=True, stop=99.0):
    return {
        "market": "stock",
        "symbol": "TTEK",
        "tf": tf,
        "signal": signal,
        "raw_signal": raw_signal,
        "setup": setup,
        "score": score,
        "backtest_eligible": eligible,
        "close": 100.0,
        "stop": stop,
        "sma20": 101.0,
        "sma40": 99.0,
        "sma100": 95.0,
        "sma200": 90.0,
        "dist_sma20_pct": -1.0,
        "atr_pct": 0.01,
        "relative_volume": 1.6,
        "backtest_profit_factor": 1.4,
        "backtest_buy_hold_edge_pct": 0.04,
        "backtest_trades": 14,
    }


def test_build_confluence_buys_when_one_hour_confirms_and_15m_triggers():
    scan = pd.DataFrame(
        [
            _row("15m", "BUY", "BUY", "PULLBACK", 92),
            _row("1h", "WATCH", "WATCH", "EARLY_UPTREND", 80),
            _row("2h", "WATCH", "WATCH", "TREND_CONTINUATION", 78),
            _row("4h", "WATCH", "WATCH", "TREND_CONTINUATION", 76),
        ]
    )

    out = build_confluence(scan)

    assert len(out) == 1
    assert out.loc[0, "signal"] == "BUY"
    assert out.loc[0, "action"] == "ENTER_LONG"
    assert out.loc[0, "risk_pct"] == 0.01
    assert out.loc[0, "trade_decision"] == "TRADE_FOR_10PCT"
    assert out.loc[0, "target_2pct_ok"]
    assert "1h confirma setup alcista" in out.loc[0, "reasons"]
    assert "15m da gatillo tecnico" in out.loc[0, "reasons"]
    assert out.loc[0, "higher_tf_bias"] == "CONFIRMED"
    assert out.loc[0, "higher_tf_confirmations"] == 2
    assert "2h confirma contexto alcista" in out.loc[0, "reasons"]


def test_build_confluence_marks_higher_timeframe_block():
    scan = pd.DataFrame(
        [
            _row("15m", "BUY", "BUY", "PULLBACK", 92),
            _row("1h", "WATCH", "WATCH", "EARLY_UPTREND", 80),
            _row("4h", "AVOID", "AVOID", "DOWNTREND", 30),
        ]
    )

    out = build_confluence(scan)

    assert out.loc[0, "higher_tf_bias"] == "BLOCKED"
    assert out.loc[0, "higher_tf_blocks"] == 1
    assert "4h no acompana la estructura" in out.loc[0, "reasons"]


def test_build_confluence_degrades_when_backtest_is_not_eligible():
    scan = pd.DataFrame(
        [
            _row("15m", "WATCH", "BUY", "PULLBACK", 92, eligible=False),
            _row("1h", "WATCH", "WATCH", "EARLY_UPTREND", 64, eligible=False),
        ]
    )

    out = build_confluence(scan)

    assert out.loc[0, "signal"] == "WATCH"
    assert out.loc[0, "action"] == "WAIT_FOR_TRIGGER"
    assert bool(out.loc[0, "backtest_eligible"]) is False


def test_build_confluence_waits_when_targets_do_not_justify_stop_risk():
    scan = pd.DataFrame(
        [
            _row("15m", "BUY", "BUY", "PULLBACK", 92, stop=94.0),
            _row("1h", "WATCH", "WATCH", "EARLY_UPTREND", 80, stop=94.0),
        ]
    )

    out = build_confluence(scan)

    assert out.loc[0, "signal"] == "WATCH"
    assert out.loc[0, "action"] == "WAIT_FOR_BETTER_RISK"
    assert out.loc[0, "trade_decision"] == "NO_TRADE_RISK_REWARD"
    assert not out.loc[0, "target_2pct_ok"]


def test_render_confluence_report_contains_specialized_sections():
    df = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "TTEK",
                "signal": "BUY",
                "action": "ENTER_LONG",
                "confluence_score": 90,
                "entry": 100.0,
                "stop": 96.0,
                "risk_pct": 0.04,
                "trigger_setup": "PULLBACK",
                "trigger_score": 92,
                "trend_setup": "EARLY_UPTREND",
                "trend_score": 64,
                "higher_tf_bias": "CONFIRMED",
                "htf_2h_setup": "TREND_CONTINUATION",
                "htf_2h_score": 78,
                "htf_4h_setup": "TREND_CONTINUATION",
                "htf_4h_score": 76,
                "backtest_profit_factor": 1.4,
            }
        ]
    )
    summary = build_confluence_summary(df)

    report = render_confluence_report(summary, scan_path="output/live.csv")

    assert "Specialized Confluence" in report
    assert "1h trend + 15m trigger" in report
    assert "stock TTEK" in report
    assert "HTF CONFIRMED" in report


def test_ma_confluence_cli_help_loads_root_module():
    result = subprocess.run(
        [sys.executable, "tools/ma_confluence.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Build specialized SMA" in result.stdout
