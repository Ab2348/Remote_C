from pathlib import Path
from enum import StrEnum


from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import router


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "app" / "static"

app = FastAPI(
    title="Remote C",
    version="0.3.0",
    description="Control remoto local para Arch Linux",
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "hybrid",
    }


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
