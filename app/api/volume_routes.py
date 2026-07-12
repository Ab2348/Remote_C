import asyncio
from enum import StrEnum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.controller import controller
from app.services.events import event_hub
from app.services.volume import VolumeControlError


router = APIRouter(prefix="/api/volume")


class VolumeAction(StrEnum):
    UP = "up"
    DOWN = "down"
    MUTE = "mute"


class VolumeActionRequest(BaseModel):
    action: VolumeAction


class VolumeSetRequest(BaseModel):
    volume: int = Field(ge=0, le=100)


async def _publish_volume(state: dict) -> dict:
    await event_hub.publish(
        "volume",
        {
            "volume": state["volume"],
            "muted": state["muted"],
        },
    )
    return state


@router.post("/control")
async def control_volume(request: VolumeActionRequest) -> dict:
    try:
        state = await asyncio.to_thread(
            controller.change_volume,
            request.action,
        )
        return await _publish_volume(state)
    except VolumeControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/set")
async def set_volume(request: VolumeSetRequest) -> dict:
    try:
        state = await asyncio.to_thread(
            controller.set_volume,
            request.volume,
        )
        return await _publish_volume(state)
    except VolumeControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
