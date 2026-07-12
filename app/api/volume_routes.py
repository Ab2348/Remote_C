import asyncio
from enum import StrEnum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.controller import controller
from app.services.events import event_hub
from app.services.volume import VolumeControlError


router = APIRouter(prefix="/api")


class VolumeControlAction(StrEnum):
    UP = "up"
    DOWN = "down"
    MUTE = "mute"


class VolumeControlRequest(BaseModel):
    action: VolumeControlAction


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


@router.post("/volume/control")
async def control_volume(request: VolumeControlRequest) -> dict:
    try:
        state = await asyncio.to_thread(
            controller.change_volume_state,
            request.action,
        )
        return await _publish_volume(state)
    except VolumeControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/volume/set")
async def set_volume(request: VolumeSetRequest) -> dict:
    try:
        state = await asyncio.to_thread(
            controller.set_volume,
            request.volume,
        )
        return await _publish_volume(state)
    except VolumeControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
