"""Auth-specific exceptions — a distinct type from
src/market_data/exceptions.py's MarketDataAuthError (that one is about
Kite Connect rejecting our credentials; this one is about a request not
proving its own identity to this API). Both map to 401, but conflating
them would make src/main.py's handler give a misleading error message.
"""


class AuthenticationError(Exception):
    """Raised by src/auth/dependencies.py when a request has no valid,
    unexpired Bearer token — missing header, malformed token, expired
    token, or a token for a user that no longer exists all raise this.
    """
