from enum import StrEnum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.controller import controller
from app.services.volume import VolumeControlError
from app.services.media import MediaControlError
from app.services.brightness import BrightnessControlError

from app.services.audio_routing import (
    AudioRoutingError,
    audio_routing,
)

CONTROL_ERRORS = (
    VolumeControlError,
    MediaControlError,
    BrightnessControlError,
)


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


class OutputRequest(BaseModel):
    name: str = Field(min_length=1, max_length=512)


class StreamOutputRequest(OutputRequest):
    stream_index: int = Field(ge=0)


class StreamVolumeRequest(BaseModel):
    stream_index: int = Field(ge=0)
    volume: int = Field(ge=0, le=100)


class StreamMuteRequest(BaseModel):
    stream_index: int = Field(ge=0)


@router.get("/state")
def get_state() -> dict:
    try:
        return controller.get_state()
    except CONTROL_ERRORS as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/volume")
def control_volume(request: VolumeRequest) -> dict:
    try:
        return controller.change_volume(request.action)
    except CONTROL_ERRORS as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/media")
def control_media(request: MediaRequest) -> dict:
    try:
        return controller.control_media(request.action)
    except CONTROL_ERRORS as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/brightness")
def control_brightness(request: BrightnessRequest) -> dict:
    try:
        return controller.change_brightness(request.action)
    except CONTROL_ERRORS as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/audio-routing")
def get_audio_routing() -> dict:
    try:
        return audio_routing.get_state()
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/audio-routing/default")
def set_default_output(request: OutputRequest) -> dict:
    try:
        return audio_routing.set_default(request.name)
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/audio-routing/force")
def force_audio_output(request: OutputRequest) -> dict:
    try:
        return audio_routing.force_all(request.name)
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/audio-routing/stream")
def move_audio_stream(request: StreamOutputRequest) -> dict:
    try:
        return audio_routing.move_stream(
            request.stream_index,
            request.name,
        )
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/audio-routing/stream/volume")
def set_stream_volume(request: StreamVolumeRequest) -> dict:
    try:
        return audio_routing.set_stream_volume(
            request.stream_index,
            request.volume,
        )
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/audio-routing/stream/mute")
def toggle_stream_mute(request: StreamMuteRequest) -> dict:
    try:
        return audio_routing.toggle_stream_mute(request.stream_index)
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
