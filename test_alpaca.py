import os

from alpaca.trading.client import TradingClient
from dotenv import load_dotenv


def env_bool(x, default=True):
    if x is None:
        return default
    return str(x).strip().lower() in ("1", "true", "yes", "y", "on")


def main():
    load_dotenv()
    key = os.getenv("ALPACA_API_KEY", "").strip()
    secret = (os.getenv("ALPACA_API_SECRET") or os.getenv("ALPACA_SECRET_KEY") or "").strip()
    paper = env_bool(os.getenv("ALPACA_PAPER", "true"), True)
    url_override = (
        os.getenv("ALPACA_BASE_URL") or os.getenv("ALPACA_ENDPOINT") or os.getenv("ALPACA_API_BASE_URL") or ""
    ).strip()
    expected_endpoint = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
    if url_override:
        override_lower = url_override.lower()
        mismatch = (paper and "paper-api.alpaca.markets" not in override_lower) or (
            not paper and "paper-api.alpaca.markets" in override_lower
        )
        if mismatch:
            print(f"⚠️  Ignorando endpoint override desalineado; esperado: {expected_endpoint}")
            url_override = ""

    if not key or not secret:
        raise SystemExit("❌ Faltan ALPACA_API_KEY y ALPACA_API_SECRET/ALPACA_SECRET_KEY en tu .env")

    kwargs = {"api_key": key, "secret_key": secret, "paper": paper}
    if url_override:
        kwargs["url_override"] = url_override
    try:
        client = TradingClient(**kwargs)
        acct = client.get_account()
    except Exception as exc:
        text = f"{exc.__class__.__name__}: {exc}"
        category = (
            "AUTH_INVALID"
            if any(token in text.lower() for token in ("401", "unauthorized", "invalid", "auth"))
            else "ERROR"
        )
        raise SystemExit(
            f"❌ Alpaca {category}. Revisa que ALPACA_PAPER={str(paper).lower()} coincida con {expected_endpoint} "
            "y que ALPACA_API_KEY + ALPACA_API_SECRET/ALPACA_SECRET_KEY sean del mismo modo paper/live."
        ) from exc
    print("✅ Conexión exitosa a Alpaca!")
    print("Paper mode:", paper)
    print("Endpoint esperado:", expected_endpoint)
    print("Estado:", acct.status)
    print("Cash:", acct.cash)
    print("Equity:", acct.equity)


if __name__ == "__main__":
    main()
