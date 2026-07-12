from fastapi import FastAPI

from app.api import router


app = FastAPI(
    title="Remote C",
    version="0.1.0",
    description="Control remoto local para Arch Linux",
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "simulation",
    }
