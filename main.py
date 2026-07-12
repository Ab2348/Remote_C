from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.api.volume_routes import router as volume_router
from app.services.monitors import system_event_monitors


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "app" / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await system_event_monitors.start()
    try:
        yield
    finally:
        await system_event_monitors.stop()


app = FastAPI(
    title="Remote C",
    version="0.5.0",
    description="Control remoto local para Arch Linux",
    lifespan=lifespan,
)

app.include_router(router)
app.include_router(volume_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "live",
    }


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
