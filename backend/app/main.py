"""
NBFI Contagion Simulator — API entrypoint.

Mounts routers for /api/network, /api/quarters, and /api/simulate on top
of the Phase 3/4 pipeline outputs (reconstructed network, Eisenberg-Noe
clearing, DebtRank cascading) - no algorithm logic lives here, this is
purely the HTTP layer over already-tested modules in app/services/.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import network, simulate
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Reconstructs a bilateral exposure network between banks and "
        "non-bank financial institutions, and runs Eisenberg-Noe / "
        "DebtRank contagion simulations on it."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(network.router)
app.include_router(simulate.router)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "app": settings.app_name, "phase": "5 - backend API"}