#!/usr/bin/env python3
"""Simple Playwright snapshot helper for CI.

Usage:
  python tools/ci/snapshot_playwright.py --url http://127.0.0.1:8501 --out run/streamlit_snapshot.png
"""
import argparse
import time
import sys

from playwright.sync_api import sync_playwright


def wait_for_url(url: str, timeout: int = 60) -> bool:
    import requests

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def snapshot(url: str, out: str) -> int:
    ok = wait_for_url(url, timeout=60)
    if not ok:
        print(f"URL {url} did not respond in time", file=sys.stderr)
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=60000)
            # allow JS to settle
            page.wait_for_timeout(2500)
            page.screenshot(path=out, full_page=True)
            print(f"Wrote snapshot to {out}")
        except Exception as e:
            print("Snapshot failed:", e, file=sys.stderr)
            return 3
        finally:
            browser.close()
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    rc = snapshot(args.url, args.out)
    sys.exit(rc)


if __name__ == "__main__":
    main()
