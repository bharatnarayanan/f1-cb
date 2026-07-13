"""Daily Zerodha Kite Connect login helper.

Kite Connect access tokens expire every day — there is no way around this,
it's how Zerodha's API works. This script walks you through getting a
fresh one each morning:

  1. Prints (and tries to open) your personal Zerodha login URL.
  2. You log in in your browser (password + 2FA), same as the Kite app.
  3. You paste back the URL you land on after logging in.
  4. This script exchanges that for today's access token and saves it into
     .env for you.
  5. It confirms everything worked by fetching one live, read-only quote.

READ-ONLY: this script only ever calls Kite's login/session-exchange and a
single quote lookup. It never places, modifies, or cancels an order, and it
never prints your api_secret or access_token to the screen or into any log
— see docs/CLAUDE.md section 2.

Run it with:  python3 scripts/kite_daily_login.py
"""

import re
import sys
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from kiteconnect import KiteConnect

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _extract_request_token(pasted: str) -> str:
    """Accept either the full redirected URL or a bare request_token."""
    pasted = pasted.strip()
    if pasted.startswith("http"):
        query = parse_qs(urlparse(pasted).query)
        tokens = query.get("request_token")
        if not tokens:
            sys.exit(
                "Couldn't find a request_token in that URL. Make sure you "
                "copied the FULL address-bar URL from right after logging in."
            )
        return tokens[0]
    return pasted


def _update_env_file(access_token: str) -> None:
    """Rewrite only the KITE_ACCESS_TOKEN line in .env, leaving everything
    else untouched. Never logs the token value.
    """
    text = ENV_PATH.read_text()
    new_line = f"KITE_ACCESS_TOKEN={access_token}"

    if re.search(r"^KITE_ACCESS_TOKEN=.*$", text, flags=re.MULTILINE):
        # A plain string `repl` would let a backslash in the token (e.g.
        # "\1", "\g<name>") be parsed as a backreference by re.sub instead
        # of literal text. A callable repl is never backslash-escaped.
        text = re.sub(r"^KITE_ACCESS_TOKEN=.*$", lambda _match: new_line, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + "\n" + new_line + "\n"

    ENV_PATH.write_text(text)


def main() -> None:
    load_dotenv(ENV_PATH)
    import os

    api_key = os.getenv("KITE_API_KEY")
    api_secret = os.getenv("KITE_API_SECRET")

    if not api_key or api_key == "your-kite-api-key-here":
        sys.exit("KITE_API_KEY missing/placeholder in .env — set it first.")
    if not api_secret or api_secret == "your-kite-api-secret-here":
        sys.exit("KITE_API_SECRET missing/placeholder in .env — set it first.")

    kite = KiteConnect(api_key=api_key)
    login_url = kite.login_url()

    print("\nStep 1: log in to Zerodha.")
    print(f"Opening in your browser: {login_url}")
    print("(If it doesn't open automatically, copy-paste that URL yourself.)\n")
    webbrowser.open(login_url)

    print("Step 2: after logging in (password + 2FA), Zerodha redirects you")
    print("to a URL that starts with your app's redirect address and")
    print("contains '?request_token=...'. Copy that WHOLE address-bar URL.\n")
    pasted = input("Paste the redirected URL here (or just the request_token): ")
    request_token = _extract_request_token(pasted)

    print("\nStep 3: exchanging it for today's access token...")
    try:
        session_data = kite.generate_session(request_token, api_secret=api_secret)
    except Exception as exc:
        sys.exit(f"Login exchange failed: {type(exc).__name__}: {exc}")

    access_token = session_data["access_token"]
    _update_env_file(access_token)
    print("Saved today's access token to .env (value not shown, by design).")

    print("\nStep 4: confirming it works with one read-only quote...")
    kite.set_access_token(access_token)
    try:
        quote = kite.ltp(["NSE:NIFTY 50"])
        price = quote["NSE:NIFTY 50"]["last_price"]
    except Exception as exc:
        sys.exit(f"Token saved, but the confirmation quote failed: {type(exc).__name__}: {exc}")

    print(f"Success — NIFTY 50 last price: {price}")
    print("\nIf the app (docker compose) is already running, apply the new")
    print("token with:  docker compose up -d api")


if __name__ == "__main__":
    main()
