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
    secret = os.getenv("ALPACA_SECRET_KEY", "").strip()
    paper = env_bool(os.getenv("ALPACA_PAPER", "true"), True)

    if not key or not secret:
        raise SystemExit("❌ Faltan ALPACA_API_KEY o ALPACA_SECRET_KEY en tu .env")

    client = TradingClient(api_key=key, secret_key=secret, paper=paper)
    acct = client.get_account()
    print("✅ Conexión exitosa a Alpaca!")
    print("Paper mode:", paper)
    print("Estado:", acct.status)
    print("Cash:", acct.cash)
    print("Equity:", acct.equity)


if __name__ == "__main__":
    main()
