from enum import StrEnum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.controller import controller
from app.services.volume import VolumeControlError


router = APIRouter(prefix="/api")


class VolumeAction(StrEnum):
    UP = "up"
    DOWN = "down"
    MUTE = "mute"


class MediaAction(StrEnum):
    PLAY_PAUSE = "play_pause"
    PREVIOUS = "previous"
    NEXT = "next"


class BrightnessAction(StrEnum):
    UP = "up"
    DOWN = "down"


class VolumeRequest(BaseModel):
    action: VolumeAction


class MediaRequest(BaseModel):
    action: MediaAction


class BrightnessRequest(BaseModel):
    action: BrightnessAction


@router.get("/state")
def get_state() -> dict:
    try:
        return controller.get_state()
    except VolumeControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/volume")
def control_volume(request: VolumeRequest) -> dict:
    try:
        return controller.change_volume(request.action)
    except VolumeControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/media")
def control_media(request: MediaRequest) -> dict:
    return controller.control_media(request.action)


@router.post("/brightness")
def control_brightness(request: BrightnessRequest) -> dict:
    return controller.change_brightness(request.action)