import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.controller import controller
from app.services.events import event_hub
from app.services.volume import VolumeControlError


router = APIRouter(prefix="/api")


class VolumeSetRequest(BaseModel):
    volume: int = Field(ge=0, le=100)


@router.post("/volume/set")
async def set_volume(request: VolumeSetRequest) -> dict:
    try:
        state = await asyncio.to_thread(
            controller.set_volume,
            request.volume,
        )
        await event_hub.publish(
            "volume",
            {
                "volume": state["volume"],
                "muted": state["muted"],
            },
        )
        return state
    except VolumeControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
