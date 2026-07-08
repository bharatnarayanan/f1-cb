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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings

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

# Route modules (auth, market data, patterns, recommendations, journal,
# paper-trades, strategies, alerts, risk-settings — see docs/api_routes.md)
# mount here as they're implemented:
#   from src.routes import auth, market, recommendations, journal, strategies
#   app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
#   ...


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "safety_notice": SAFETY_NOTICE}
