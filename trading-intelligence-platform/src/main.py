"""Trading Intelligence Platform API entrypoint.

Read-only market-data decision-support tool — NO order placement, NO
real-money execution path anywhere in this codebase. See docs/CLAUDE.md
section 2 before adding any route. Execution modes are `paper` (simulated
fills) and `live_manual` (recommend only, founder executes manually) —
there is no `live_algo` mode.

Run locally: uvicorn src.main:app --reload
Run via Docker: see docker-compose.yml (service `api`).
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.cache.redis_client import RedisCache, get_redis_cache
from src.config import Settings, get_settings
from src.db.session import get_db
from src.market_data.exceptions import (
    MarketDataAuthError,
    MarketDataInvalidRequest,
    MarketDataUnavailable,
)
from src.routes import market

SAFETY_NOTICE = (
    "Read-only market data. No order placement. No real-money execution "
    "path exists in this system — recommendations are informational; "
    "trades are placed manually by the user in their own broker app."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # The intelligence pipeline (pattern detection, negation prediction,
    # scoring, alert dispatch) runs in the dedicated `worker` service
    # (docker-compose.yml), not in this process, so the API stays
    # stateless and only ever reads what the worker last wrote (plus
    # lightweight on-demand read-only quote lookups).
    app.state.settings = settings
    yield


app = FastAPI(
    title="Trading Intelligence Platform API",
    version="0.1.0-MVP",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(MarketDataUnavailable)
def _market_data_unavailable_handler(request: Request, exc: MarketDataUnavailable) -> JSONResponse:
    # Per docs/CLAUDE.md section 6: skip, never fabricate — surface a clear
    # 503 rather than a recommendation/response built on missing data.
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "code": "data_source_unavailable"},
    )


@app.exception_handler(MarketDataAuthError)
def _market_data_auth_error_handler(request: Request, exc: MarketDataAuthError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": str(exc), "code": "data_source_auth_error"},
    )


@app.exception_handler(MarketDataInvalidRequest)
def _market_data_invalid_request_handler(request: Request, exc: MarketDataInvalidRequest) -> JSONResponse:
    # Permanent, non-transient rejection (bad symbol, insufficient scope) —
    # a 400, not a 503, since retrying identically will never succeed.
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "code": "data_source_invalid_request"},
    )


@app.exception_handler(SQLAlchemyError)
def _sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    # Per docs/CLAUDE.md section 6: never fabricate — surface a clean 503
    # rather than letting a DB write failure leak as an unhandled 500.
    return JSONResponse(
        status_code=503,
        content={"detail": "Database write failed.", "code": "storage_unavailable"},
    )


# Route modules (auth, patterns, recommendations, journal, paper-trades,
# strategies, alerts, risk-settings — see docs/api_routes.md) mount here as
# later phases implement them:
#   from src.routes import auth, recommendations, journal, strategies
#   app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(market.router)


@app.get("/health")
def health(
    db: Session = Depends(get_db),
    cache: RedisCache = Depends(get_redis_cache),
    settings: Settings = Depends(get_settings),
) -> dict:
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        redis_ok = cache.ping()
    except Exception:
        redis_ok = False

    kite_configured = bool(settings.kite_api_key and settings.kite_access_token)

    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "database": "ok" if db_ok else "unreachable",
        "redis": "ok" if redis_ok else "unreachable",
        # Kite is checked for configuration only here, not a live call —
        # use GET /api/v1/market/quote/{symbol} to confirm real connectivity.
        "kite": "configured" if kite_configured else "not_configured",
        # "sample": in-memory mock data, no Zerodha creds needed (Phase 2
        # default). "live": real Kite Connect calls. See src/config.py.
        "data_mode": settings.data_mode,
        "safety_notice": SAFETY_NOTICE,
    }
