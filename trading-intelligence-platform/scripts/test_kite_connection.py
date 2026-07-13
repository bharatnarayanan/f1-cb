"""Read-only smoke test: confirms Kite Connect creds in .env work by
fetching one live quote. No order-placement calls exist here or anywhere
in this codebase — see docs/CLAUDE.md section 2.
"""

import os
import sys

from dotenv import load_dotenv
from kiteconnect import KiteConnect

load_dotenv()

api_key = os.getenv("KITE_API_KEY")
access_token = os.getenv("KITE_ACCESS_TOKEN")

if not api_key or api_key == "your-kite-api-key-here":
    sys.exit("KITE_API_KEY missing/placeholder in .env — set it first.")
if not access_token or access_token == "your-kite-access-token-here":
    sys.exit("KITE_ACCESS_TOKEN missing/placeholder in .env — set it first.")

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

quote = kite.ltp(["NSE:NIFTY 50"])
print(quote)
