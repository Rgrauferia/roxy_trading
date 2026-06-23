"""Streamlit dashboard: tabbed view for crypto, stocks, real estate and news.

This file reads the latest `*_tech_*.csv` outputs, scans the `db/ohlcv`
table for historical prices (if available), and shows a small detail
view with a price chart and annotated entry/stop/tp lines.
"""
from __future__ import annotations

import json
from glob import glob
from pathlib import Path
from typing import Optional
from datetime import datetime

import pandas as pd
import sqlite3
import streamlit as st
import altair as alt

from config import TOP_PICKS_FILE, ENABLE_GROK_CODE_FAST
import storage
import grok_control
import auth


def latest_file(pattern: str) -> Optional[str]:
    files = glob(pattern)
    if not files:
        return None
    # choose by modified time
    files.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return files[0]


def load_latest_tech_df(kind: str) -> pd.DataFrame:
    """Load the most recent tech CSV for `kind` in `output/`.

    kind should be 'crypto' or 'stocks'.
    """
    pattern = f"output/{kind}_tech_*.csv" if kind == "stocks" else f"output/{kind}_tech_*.csv"
    path = latest_file(pattern)
    if not path:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def get_ohlcv(symbol: str) -> pd.DataFrame:
    """Query the local `db/roxy.db` ohlcv table for `symbol`.

    Returns a DataFrame indexed by datetime with open/high/low/close/volume.
    """
    conn = sqlite3.connect(storage.DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ts, open, high, low, close, volume FROM ohlcv WHERE symbol = ? ORDER BY ts",
            (symbol, ),
        )
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])  # type: ignore
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    return df


def read_summary_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def read_latest_alert_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text()


def show_market_tab(kind: str) -> None:
    df = load_latest_tech_df(kind)
    if df.empty:
        st.info(f"No {kind} data available in `output/`.")
        return

    # normalize market column variations
    if "market" in df.columns:
        df = df.copy()
        # keep only relevant rows
    st.write(f"Latest {kind.capitalize()} scan — {len(df)} rows")

    # top picks in this market
    if "rank_score" in df.columns:
        top = df.sort_values("rank_score", ascending=False).head(10)
        st.subheader("Top recommendations")
        st.dataframe(top[[c for c in ["symbol", "tf", "signal", "score", "rank_score", "entry", "stop", "tp2"] if c in top.columns]])

    # pick a symbol to inspect
    symbols = sorted(df["symbol"].unique())
    choice = st.selectbox(f"Select {kind} symbol", symbols)
    row = df[df["symbol"] == choice].iloc[0]

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(f"{choice} — {row.get('signal', '')} | score {row.get('score', '')}")
        ohlcv = get_ohlcv(choice)
        if not ohlcv.empty:
            # build a candlestick chart with zoom/tooltip
            df_cs = ohlcv.reset_index().rename(columns={"ts": "time"})
            df_cs["time_str"] = df_cs["time"].dt.strftime("%Y-%m-%d %H:%M")

            base = alt.Chart(df_cs).encode(x=alt.X("time:T", title="Time"))

            rule = base.mark_rule().encode(
                y=alt.Y("low:Q", title="Price"),
                y2="high:Q",
                tooltip=[alt.Tooltip("time_str:N", title="Time"), alt.Tooltip("open:Q"), alt.Tooltip("high:Q"), alt.Tooltip("low:Q"), alt.Tooltip("close:Q"), alt.Tooltip("volume:Q")],
            )

            bar = base.mark_bar().encode(
                y=alt.Y("open:Q", title=""),
                y2="close:Q",
                color=alt.condition("datum.open <= datum.close", alt.value("green"), alt.value("red")),
                tooltip=[alt.Tooltip("time_str:N", title="Time"), alt.Tooltip("open:Q"), alt.Tooltip("high:Q"), alt.Tooltip("low:Q"), alt.Tooltip("close:Q"), alt.Tooltip("volume:Q")],
            )

            selection = alt.selection_interval(bind="scales")

            chart = (rule + bar).properties(height=360).add_selection(selection)

            # overlay horizontal lines for entry/stop/tp2
            overlays = []
            for fld, color, label in (("entry", "green", "Entry"), ("stop", "red", "Stop"), ("tp2", "blue", "TP2")):
                val = row.get(fld)
                if val is not None and pd.notna(val):
                    overlays.append(alt.Chart(pd.DataFrame({"y": [float(val)], "label": [label]})).mark_rule(color=color, size=1).encode(y="y:Q"))
                    overlays.append(alt.Chart(pd.DataFrame({"y": [float(val)], "label": [label]})).mark_text(align="left", dx=5, dy=-5, color=color).encode(y="y:Q", text=alt.Text("label:N")))

            for o in overlays:
                chart = chart + o

            st.altair_chart(chart.interactive(), use_container_width=True)
        else:
            st.info("No historical OHLCV in local DB for this symbol — showing latest metrics.")
            st.metric("Entry", row.get("entry", "n/a"))
            st.metric("Stop", row.get("stop", "n/a"))
            st.metric("TP2", row.get("tp2", "n/a"))

    with col2:
        st.subheader("Trade setup")
        signal = str(row.get("signal", "")).upper()
        if signal == "BUY":
            st.success(f"Signal: {signal}")
        elif signal == "WATCH":
            st.info(f"Signal: {signal}")
        else:
            st.warning(f"Signal: {signal}")

        st.write(f"**Score:** {row.get('score', '')}  ")
        st.write(f"**Rank:** {row.get('rank_score', '')}  ")
        st.write(f"**RR (tp2):** {row.get('rr_tp2', '')}  ")
        st.markdown("---")
        st.subheader("Simulation")
        user = st.session_state.get("user", "anon")
        sizing_mode = st.selectbox("Sizing mode", options=["Units", "% Equity"])
        if sizing_mode == "% Equity":
            try:
                equity = storage.get_account_equity(user)
            except Exception:
                equity = 10000.0
            pct = st.slider("Percent of equity", 1, 100, 10)
            price = float(row.get("entry") or (ohlcv["close"].iloc[-1] if not ohlcv.empty else 0.0))
            qty = (equity * (pct / 100.0)) / (price if price > 0 else 1.0)
        else:
            qty = st.number_input("Position size (units)", min_value=0.0, value=1.0, step=0.1)
            price = float(row.get("entry") or (ohlcv["close"].iloc[-1] if not ohlcv.empty else 0.0))

        if st.button("Simulate BUY"):
            try:
                pid = storage.open_sim_position(user, choice, float(qty), float(price), note="simulated via UI")
                storage.save_simulated_trade(user, choice, "BUY", float(qty), float(price), note=f"open_pos:{pid}")
                # snapshot equity including unrealized after opening
                try:
                    storage.snapshot_account_point(user)
                except Exception:
                    pass
                st.success(f"Opened simulated position #{pid}")
            except Exception as e:
                st.error(f"Failed to open simulated position: {e}")

        if st.button("Simulate SELL (close)"):
            try:
                pnl = storage.close_sim_position_by_symbol(user, choice, float(qty), float(price))
                storage.save_simulated_trade(user, choice, "SELL", float(qty), float(price), note=f"close_qty={qty}")
                # snapshot equity after realized P&L applied
                try:
                    storage.snapshot_account_point(user)
                except Exception:
                    pass
                st.success(f"Closed positions for {qty} units, realized P&L {pnl:.2f}")
            except Exception as e:
                st.error(f"Failed to close simulated position: {e}")

        st.subheader("Open simulated positions")
        open_pos = storage.get_open_positions(user)
        if open_pos:
            rows = []
            last_price = float(ohlcv["close"].iloc[-1]) if not ohlcv.empty else price
            for pid, ts_open, usr, sym, pqty, entry_price, note in open_pos:
                unreal = (last_price - float(entry_price)) * float(pqty)
                rows.append({"id": pid, "ts_open": ts_open, "symbol": sym, "qty": pqty, "entry": entry_price, "last": last_price, "unreal_pnl": unreal, "note": note})
            df_open = pd.DataFrame(rows)
            st.table(df_open)
        else:
            st.write("No open simulated positions.")

        # show equity curve for signed-in user
        if user:
            pts = storage.get_equity_series(user)
            if pts:
                df_eq = pd.DataFrame(pts, columns=["ts", "equity"])  # type: ignore
                df_eq["ts"] = pd.to_datetime(df_eq["ts"])
                eq_chart = alt.Chart(df_eq).mark_line(color="#2b8cbe").encode(x=alt.X("ts:T", title="Time"), y=alt.Y("equity:Q", title="Equity"))
                st.subheader("Equity Curve")
                st.altair_chart(eq_chart.properties(height=200), use_container_width=True)
            else:
                st.write("No equity history for this user yet.")

        st.subheader("Recent simulated trades (audit)")
        rows = storage.get_simulated_trades(limit=20)
        if rows:
            df_tr = pd.DataFrame(rows, columns=["id", "ts", "user", "symbol", "side", "qty", "price", "note"])  # type: ignore
            st.table(df_tr)
        else:
            st.write("No simulated trades yet.")

        # Grok suggestion
        from grok_integration import generate_suggestion

        if st.button("Generate Grok suggestion"):
            ctx = {"score": row.get("score"), "signal": row.get("signal")}
            sugg = generate_suggestion(choice, ctx)
            st.info(sugg.get("text"))
            st.write("Confidence:", f"{sugg.get('confidence'):.2f}")


def show_news_tab() -> None:
    st.subheader("Latest Alert")
    last = read_latest_alert_text("alerts/latest_alert.txt")
    if last:
        st.info(last)
    else:
        st.write("No latest alert file found.")

    st.subheader("Latest Summary JSON")
    summary = read_summary_json("alerts/latest_summary.json")
    if summary:
        st.json(summary)
    else:
        st.write("No latest summary JSON found.")

    st.subheader("News & Suggestions")
    # simple suggestions: echo top picks with a short suggestion sentence
    top_picks = read_summary_json("alerts/latest_summary.json").get("top_picks", [])
    suggestions = []
    for p in top_picks[:10]:
        symbol = p.get("symbol")
        signal = p.get("signal")
        if symbol and signal:
            suggestions.append(f"{symbol}: Current suggestion — {signal}. Consider watching entry {p.get('entry')} and stop {p.get('stop')}")

    if suggestions:
        for s in suggestions:
            st.write("- ", s)
    else:
        st.write("No suggestions available.")

    # RSS / news fetcher
    st.markdown("---")
    st.subheader("External News Feeds")
    from news import fetch_news, save_highlights

    with st.expander("Fetch latest headlines"):
        max_items = st.slider("Headlines", 5, 50, 10)
        try:
            headlines = fetch_news(max_items=max_items)
        except Exception as e:
            st.error(f"Failed to fetch news: {e}")
            headlines = []

        if not headlines:
            st.write("No items fetched.")
        else:
            sources = sorted({h.get("source", "") for h in headlines})
            sel = st.multiselect("Sources", options=sources, default=sources)
            sent_threshold = st.slider("Minimum sentiment", -1.0, 1.0, 0.0, 0.1)

            filtered = [h for h in headlines if h.get("source") in sel and h.get("sentiment", 0) >= sent_threshold]

            st.write(f"Showing {len(filtered)} / {len(headlines)} items")

            to_save = []
            for h in filtered:
                s = h.get("sentiment", 0.0)
                if s > 0.2:
                    sentiment_mark = f"🟢 {s:.2f}"
                elif s < -0.2:
                    sentiment_mark = f"🔴 {s:.2f}"
                else:
                    sentiment_mark = f"🟡 {s:.2f}"

                st.markdown(f"**[{h['source']}]** {sentiment_mark} [{h['title']}]({h['link']})")
                st.write(h.get("summary", "")[:500])
                if st.button(f"Save highlight: {h.get('title')[:60]}", key=h.get("link")):
                    to_save.append(h)
                    st.success("Saved")
                st.write("---")

            if st.button("Save all visible highlights") and filtered:
                try:
                    save_highlights(filtered)
                    st.success(f"Saved {len(filtered)} items to alerts/news_highlights.json")
                except Exception as e:
                    st.error(f"Failed to save highlights: {e}")

    # Saved highlights review
    st.markdown("---")
    st.subheader("Saved Highlights")
    highlights_path = Path("alerts/news_highlights.json")
    if highlights_path.exists():
        try:
            saved = json.loads(highlights_path.read_text())
        except Exception:
            saved = []
    else:
        saved = []

    if not saved:
        st.write("No saved highlights yet.")
    else:
        for i, h in enumerate(list(saved)):
            st.markdown(f"**{h.get('source','')}** [{h.get('title','')}]({h.get('link','')}) — sentiment {h.get('sentiment',0):+.2f}")
            if st.button(f"Remove", key=f"rm_{i}"):
                try:
                    saved.pop(i)
                    highlights_path.write_text(json.dumps(saved, indent=2))
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Failed to remove: {e}")
            st.write(h.get("summary","")[:400])
            st.write("---")

        if st.button("Export saved highlights to CSV"):
            df = pd.DataFrame(saved)
            outp = Path("output/news_highlights.csv")
            outp.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(outp, index=False)
            st.success(f"Wrote {outp}")


def main() -> None:
    st.set_page_config(page_title="Roxy Trading Dashboard", layout="wide")
    st.title("Roxy Trading — Dashboard")

    st.sidebar.header("Quick Links")
    st.sidebar.write("Data files in `output/` and `alerts/` are used to populate this dashboard.")

    st.sidebar.markdown("**Snapshot Service**")
    if st.sidebar.button("Run snapshot now (server)"):
        try:
            # if user signed in, snapshot their account; else snapshot all
            u = st.session_state.get("user")
            if u:
                val = storage.snapshot_account_point(u)
                st.sidebar.success(f"Snapshot for {u}: {val:.2f}")
            else:
                # run for all users
                import tools.account_snapshot_service as svc
                svc.snapshot_all(storage.DB_PATH)
                st.sidebar.success("Snapshot run for all users")
        except Exception as e:
            st.sidebar.error(f"Snapshot failed: {e}")

    st.sidebar.markdown("Run the background snapshot service with Docker:")
    st.sidebar.code("docker-compose up -d snapshot")

    # Local start/stop controls (development) with admin token
    st.sidebar.markdown("**Local snapshot process**")
    import tools.process_manager as pm

    interval = st.sidebar.number_input("Interval (minutes)", min_value=1, max_value=60, value=5)
    admin_token_input = st.sidebar.text_input("Admin token (for promotion)", type="password")
    # determine admin via stored role
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    # if user signed in, check role from storage
    user = st.session_state.get("user")
    try:
        if user and storage.is_admin(user):
            st.session_state.is_admin = True
    except Exception:
        pass

    # Allow bootstrap promotion via ADMIN_TOKEN env var: promotes current signed-in user to admin
    try:
        from config import ADMIN_TOKEN, ADMIN_ORGS
        if ADMIN_TOKEN and admin_token_input and admin_token_input == ADMIN_TOKEN:
            if user:
                try:
                    storage.set_user_role(user, "admin", actor=user)
                    st.session_state.is_admin = True
                    st.sidebar.success(f"User {user} promoted to admin")
                except Exception:
                    st.sidebar.error("Failed to promote user to admin in storage")
            else:
                st.sidebar.warning("Sign in first to use admin token promotion")
        # If ADMIN_ORGS configured, and user has an access token in session, auto-grant admin when signing in
        if not st.session_state.is_admin and user and st.session_state.get("access_token") and 'ADMIN_ORGS' in globals():
            try:
                token = st.session_state.get("access_token")
                orgs = auth.get_user_orgs(token)
                cfg_orgs = [o.strip() for o in (ADMIN_ORGS or "").split(",") if o.strip()]
                if any(o in cfg_orgs for o in orgs):
                    storage.set_user_role(user, "admin", actor="oauth")
                    st.session_state.is_admin = True
                    st.sidebar.success(f"User {user} auto-promoted to admin via GitHub org membership")
            except Exception:
                pass
    except Exception:
        pass

    has_admin = bool(st.session_state.is_admin)

    # Snapshot history (user-level and global)
    st.sidebar.markdown("**Snapshot History**")
    if st.session_state.get("user"):
        try:
            user_pts = storage.get_equity_series(st.session_state.user)
            if user_pts:
                df_pts = pd.DataFrame(user_pts, columns=["ts", "equity"])  # type: ignore
                df_pts["ts"] = pd.to_datetime(df_pts["ts"])
                st.sidebar.write(f"Last {len(df_pts)} points for {st.session_state.user}")
                st.sidebar.table(df_pts.tail(5))
                st.sidebar.write("Latest:", str(df_pts["ts"].iloc[-1]))
            else:
                st.sidebar.write("No snapshots for your account yet.")
        except Exception:
            st.sidebar.write("No snapshot data available.")
    else:
        st.sidebar.write("Sign in to view your snapshot history.")

    # show all accounts summary
    st.sidebar.markdown("**All accounts**")
    try:
        acct_rows = storage.list_accounts()
        if acct_rows:
            for user, created_ts, equity in acct_rows[:10]:
                role = storage.get_user_role(user)
                st.sidebar.write(f"{user} ({role}): {equity:.2f} (created {created_ts})")
        else:
            st.sidebar.write("No accounts registered yet.")
    except Exception:
        st.sidebar.write("Unable to list accounts.")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Start snapshot"):
            if not has_admin:
                st.sidebar.error("Admin token required to start service")
            else:
                try:
                    pid = pm.start_snapshot_service(interval=int(interval), run_once=False)
                    st.sidebar.success(f"Started snapshot pid={pid}")
                except Exception as e:
                    st.sidebar.error(f"Failed to start: {e}")
    with col2:
        if st.button("Stop snapshot"):
            if not has_admin:
                st.sidebar.error("Admin token required to stop service")
            else:
                try:
                    ok = pm.stop_snapshot_service()
                    if ok:
                        st.sidebar.success("Stopped snapshot service")
                    else:
                        st.sidebar.info("No snapshot service running")
                except Exception as e:
                    st.sidebar.error(f"Failed to stop: {e}")

    # Small Grok model toggle (writes .grok_settings.json)
    st.sidebar.markdown("**Grok Code Fast 1**")
    enabled_local = grok_control.is_enabled() or ENABLE_GROK_CODE_FAST
    if enabled_local:
        st.sidebar.success("Grok Code Fast 1: ENABLED")
    else:
        st.sidebar.info("Grok Code Fast 1: disabled")

    if st.sidebar.button("Toggle Grok Code Fast 1"):
        # flip the on-disk setting and show confirmation
        new_state = not grok_control.is_enabled()
        grok_control.apply_enable_for_all(new_state)
        st.experimental_rerun()

    # Admin management panel: allow admins to change roles
    if has_admin:
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Admin: Manage Roles**")
        try:
            users = [r[0] for r in storage.list_accounts()]
        except Exception:
            users = []
        target = st.sidebar.selectbox("Select user to edit role", options=[""] + users)
        new_role = st.sidebar.selectbox("Role", options=["user", "admin"], index=0)
        if st.sidebar.button("Set role") and target:
            try:
                storage.set_user_role(target, new_role, actor=st.session_state.get("user"))
                st.sidebar.success(f"Set {target} -> {new_role}")
            except Exception as e:
                st.sidebar.error(f"Failed to set role: {e}")

        # show recent role audit entries
        st.sidebar.markdown("**Role change audit**")
        try:
            rows = storage.list_role_audit(limit=50)
            if rows:
                import pandas as _pd
                df_a = _pd.DataFrame(rows, columns=["id", "actor", "target_user", "old_role", "new_role", "ts"])  # type: ignore
                st.sidebar.dataframe(df_a.head(10))
                csv = df_a.to_csv(index=False)
                st.sidebar.download_button("Export role audit CSV", data=csv, file_name="role_audit.csv", mime="text/csv")
            else:
                st.sidebar.write("No recent role changes.")
        except Exception:
            st.sidebar.write("Unable to read role audit.")
        # server-side export: write CSV to output/ so it can be served by a static server
        try:
            outp = Path("output")
            outp.mkdir(parents=True, exist_ok=True)
            if st.sidebar.button("Export audit CSV to server output"):
                fn = outp / f"role_audit_export_{st.session_state.get('user','admin')}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
                df_a.to_csv(fn, index=False)
                st.sidebar.success(f"Wrote {fn}")
                st.sidebar.write("If you run a static file server for `output/`, download at:")
                st.sidebar.write(str(fn))
        except Exception:
            pass

    # --- Login-like sidebar
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        with st.sidebar.form("login_form"):
            st.markdown("## Sign in")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
            if submitted:
                # Basic local auth simulation: accept any non-empty username
                if username.strip():
                    st.session_state.user = username.strip()
                    st.experimental_rerun()
                else:
                    st.sidebar.error("Enter a username to sign in.")
        # GitHub device-flow sign-in (requires GITHUB_CLIENT_ID env var)
        if st.sidebar.button("Sign in with GitHub (device code)"):
            try:
                with st.spinner("Starting GitHub device flow — follow instructions shown below"):
                    df = auth.github_start_device_flow()
                # store device flow state in session to allow polling
                st.session_state._gh_device = df
                st.sidebar.success("Device flow started — follow instructions below")
            except Exception as e:
                st.sidebar.error(f"GitHub sign-in failed: {e}")

        # If device flow started, show user_code and verification URI and allow polling
        if st.session_state.get("_gh_device"):
            gh = st.session_state.get("_gh_device")
            ver = gh.get("verification_uri_complete") or gh.get("verification_uri")
            st.sidebar.markdown("**Complete GitHub sign-in**")
            st.sidebar.write("Open the verification URL and enter the code below:")
            if ver:
                st.sidebar.markdown(f"{ver}")
            st.sidebar.info(f"Code: {gh.get('user_code')}")
            if st.sidebar.button("Poll GitHub for completion"):
                try:
                    with st.spinner("Waiting for GitHub authorization..."):
                        res = auth.github_poll_device_flow(gh.get("device_code"))
                    st.session_state.user = res.user
                    st.session_state.access_token = res.access_token
                    try:
                        storage.create_account_if_missing(res.user)
                    except Exception:
                        pass
                    # clear device flow state
                    st.session_state.pop("_gh_device", None)
                    st.success(f"Signed in as {res.user}")
                    st.experimental_rerun()
                except Exception as e:
                    st.sidebar.error(f"GitHub sign-in polling failed: {e}")

        # Redirect-based OAuth helper (requires running tools/oauth_server.py)
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Sign in with GitHub (redirect)**")
        if st.sidebar.button("Start redirect OAuth (open local server)"):
            try:
                port = 5000
                redirect_uri = f"http://127.0.0.1:{port}/callback"
                url = auth.start_oauth_flow("github", redirect_uri)
                st.session_state._gh_redirect_url = url
                st.sidebar.success("Redirect flow started — open the authorize URL in your browser")
            except Exception as e:
                st.sidebar.error(f"Redirect flow failed: {e}")

        if st.session_state.get("_gh_redirect_url"):
            st.sidebar.markdown("Open this URL to authorize:")
            st.sidebar.write(st.session_state.get("_gh_redirect_url"))
            if st.sidebar.button("Check for callback result"):
                try:
                    import json

                    p = Path("run/oauth_callback.json")
                    if p.exists():
                        j = json.loads(p.read_text())
                        st.session_state.user = j.get("login")
                        st.session_state.access_token = j.get("access_token")
                        try:
                            storage.create_account_if_missing(st.session_state.user)
                        except Exception:
                            pass
                        p.unlink()
                        st.success(f"Signed in as {st.session_state.user}")
                        st.experimental_rerun()
                    else:
                        st.info("No callback found yet. Complete authorization in the browser and try again.")
                except Exception as e:
                    st.sidebar.error(f"Failed to read callback: {e}")
    else:
        st.sidebar.markdown(f"**Signed in as:** {st.session_state.user}")
        try:
            storage.create_account_if_missing(st.session_state.user)
        except Exception:
            pass
        if st.sidebar.button("Sign out"):
            st.session_state.user = None
            st.experimental_rerun()

    tabs = st.tabs(["Cryptocurrencies", "Stocks", "Real Estate", "News", "Top Picks", "Execution"])  # type: ignore

    with tabs[0]:
        show_market_tab("crypto")
    with tabs[1]:
        show_market_tab("stocks")
    with tabs[2]:
        st.write("Real Estate — placeholder list")
        # For now list weekly report files as real-estate-like suggestions
        files = sorted(glob("alerts/weekly_report_*.txt"), reverse=True)
        if files:
            for f in files[:5]:
                st.write(f)
        else:
            st.write("No weekly reports found in alerts/.")
    with tabs[3]:
        show_news_tab()
    with tabs[4]:
        st.header("Top Picks")
        p = Path(TOP_PICKS_FILE)
        if p.exists():
            st.text(p.read_text())
        else:
            st.info("No top picks yet.")
    # Snapshots tab
    tabs.append(st.tab("Snapshots"))  # type: ignore
    # Execution tab (paper trading adapter)
    with tabs[5]:
        st.header("Execution — Paper Trading")
        st.write("Place orders via the simple paper trader adapter. Trades are persisted in `db/roxy.db` as simulated trades and positions.")
        user = st.session_state.get("user") or st.text_input("Execution user (will create account)")
        if user:
            try:
                storage.create_account_if_missing(user)
            except Exception:
                pass

            from adapters.paper_trader import SimplePaperTrader

            st.subheader("Execution realism")
            slippage = st.slider("Slippage %", min_value=0.0, max_value=5.0, value=0.0, step=0.1)
            fill_rate = st.slider("Fill rate %", min_value=0, max_value=100, value=100, step=5)
            # create paper trader with user-specified realism
            pt = SimplePaperTrader(user, slippage_pct=(slippage / 100.0), fill_rate=(fill_rate / 100.0))
            st.subheader("Account")
            try:
                eq = storage.get_account_equity(user)
            except Exception:
                eq = 0.0
            st.write(f"User: {user} — equity: {eq:.2f}")

            st.subheader("Place Order")
            symbol = st.text_input("Symbol", value="AAPL")
            qty = st.number_input("Quantity", min_value=0.0, value=1.0, step=0.1)
            price = st.number_input("Price", min_value=0.0, value=0.0, step=0.01)
            colb, cols = st.columns(2)
            with colb:
                if st.button("Buy (paper)"):
                    try:
                        if price <= 0:
                            st.error("Set a positive price for this simple paper execution")
                        else:
                            pid = pt.buy(symbol, qty, price)
                            st.success(f"Opened paper position #{pid} for {symbol} @ {price}")
                    except Exception as e:
                        st.error(f"Buy failed: {e}")
            with cols:
                if st.button("Sell (paper)"):
                    try:
                        if price <= 0:
                            st.error("Set a positive price for this simple paper execution")
                        else:
                            pnl = pt.sell(symbol, qty, price)
                            st.success(f"Sold {qty} {symbol}, realized P&L {pnl:.2f}")
                    except Exception as e:
                        st.error(f"Sell failed: {e}")

            st.subheader("Open Positions")
            open_pos = storage.get_open_positions(user)
            if open_pos:
                df_open = pd.DataFrame(open_pos, columns=["id", "ts_open", "user", "symbol", "qty", "entry_price", "note"])  # type: ignore
                st.table(df_open)
            else:
                st.write("No open positions for this user.")
    with tabs[-1]:
        st.header("Snapshots — account equity history")
        try:
            users = ["All"] + [r[0] for r in storage.list_accounts()]
        except Exception:
            users = ["All"]
        sel_user = st.selectbox("User", users)
        limit = st.number_input("Max rows", min_value=10, max_value=10000, value=1000)
        start = st.date_input("From", value=None)
        end = st.date_input("To", value=None)

        if st.button("Load snapshots"):
            try:
                if sel_user == "All":
                    rows = storage.get_snapshot_points(limit=int(limit))
                else:
                    # restrict viewing other users unless admin
                    if sel_user != "All" and sel_user != st.session_state.get("user") and not has_admin:
                        st.error("Permission denied: admin required to view other users' snapshots")
                        rows = []
                    else:
                        rows = storage.get_snapshot_points(user=sel_user, limit=int(limit))
                import io

                if not rows:
                    st.info("No snapshot points found")
                else:
                    # normalize rows to DataFrame
                    df = pd.DataFrame(rows, columns=["user", "ts", "equity"])  # type: ignore
                    df["ts"] = pd.to_datetime(df["ts"])
                    if start:
                        df = df[df["ts"] >= pd.to_datetime(start)]
                    if end:
                        df = df[df["ts"] <= pd.to_datetime(end)]
                    st.write(f"Showing {len(df)} rows")
                    st.dataframe(df.sort_values(["user", "ts"]))

                    # CSV export
                    csv = df.to_csv(index=False)
                    st.download_button("Export CSV", data=csv, file_name="snapshots.csv", mime="text/csv")
                    # JSON export
                    js = df.to_dict(orient="records")
                    st.download_button("Export JSON", data=json.dumps(js), file_name="snapshots.json", mime="application/json")

                    # interactive chart
                    try:
                        chart_df = df.copy()
                        if "user" not in chart_df.columns:
                            chart_df["user"] = sel_user
                        chart = alt.Chart(chart_df).mark_line().encode(x=alt.X("ts:T", title="Time"), y=alt.Y("equity:Q", title="Equity"), color="user:N")
                        st.altair_chart(chart.interactive(), use_container_width=True)
                    except Exception:
                        pass
                    # admin exports to server `output/`
                    if has_admin:
                        if st.button("Export visible to server output"):
                            outp = Path("output")
                            outp.mkdir(parents=True, exist_ok=True)
                            fn = outp / f"snapshots_export_{st.session_state.get('user','admin')}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
                            df.to_csv(fn, index=False)
                            st.success(f"Wrote {fn}")
            except Exception as e:
                st.error(f"Failed to load snapshots: {e}")


if __name__ == "__main__":
    main()
