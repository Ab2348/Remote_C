import asyncio
import json
from enum import StrEnum

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.audio_routing import AudioRoutingError, audio_routing
from app.services.brightness import BrightnessControlError
from app.services.controller import controller
from app.services.events import event_hub
from app.services.media import MediaControlError
from app.services.volume import VolumeControlError


CONTROL_ERRORS = (
    VolumeControlError,
    MediaControlError,
    BrightnessControlError,
)
EVENT_ERRORS = (*CONTROL_ERRORS, AudioRoutingError)


router = APIRouter(prefix="/api")


class VolumeAction(StrEnum):
    UP = "up"
    DOWN = "down"
    MUTE = "mute"


class MediaAction(StrEnum):
    PLAY_PAUSE = "play_pause"
    PREVIOUS = "previous"
    NEXT = "next"


class MediaSessionAction(StrEnum):
    PLAY_PAUSE = "play_pause"
    PREVIOUS = "previous"
    NEXT = "next"
    SEEK_BACKWARD = "seek_backward"
    SEEK_FORWARD = "seek_forward"


class BrightnessAction(StrEnum):
    UP = "up"
    DOWN = "down"


class VolumeRequest(BaseModel):
    action: VolumeAction


class MediaRequest(BaseModel):
    action: MediaAction


class MediaSessionRequest(BaseModel):
    player: str = Field(min_length=1, max_length=256)
    action: MediaSessionAction


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


def _sse_event(event_type: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data}\n\n"


def _volume_payload(state: dict) -> dict:
    return {
        "volume": state["volume"],
        "muted": state["muted"],
    }


def _media_payload(state: dict) -> dict:
    return {
        key: state[key]
        for key in (
            "playing",
            "playback_status",
            "current_track",
            "media_sessions",
        )
    }


def _brightness_payload(state: dict) -> dict:
    return {"brightness": state["brightness"]}


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    async def stream():
        async with event_hub.subscribe() as queue:
            try:
                state, routing = await asyncio.gather(
                    asyncio.to_thread(controller.get_state),
                    asyncio.to_thread(audio_routing.get_state),
                )
            except EVENT_ERRORS as error:
                yield _sse_event("server-error", {"detail": str(error)})
                return

            yield _sse_event(
                "snapshot",
                {"state": state, "audio_routing": routing},
            )

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event_type, payload = await asyncio.wait_for(
                        queue.get(),
                        timeout=15,
                    )
                    yield _sse_event(event_type, payload)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/state")
def get_state() -> dict:
    try:
        return controller.get_state()
    except CONTROL_ERRORS as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/volume")
async def control_volume(request: VolumeRequest) -> dict:
    try:
        state = await asyncio.to_thread(
            controller.change_volume,
            request.action,
        )
        await event_hub.publish("volume", _volume_payload(state))
        return state
    except CONTROL_ERRORS as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/media")
async def control_media(request: MediaRequest) -> dict:
    try:
        state = await asyncio.to_thread(
            controller.control_media,
            request.action,
        )
        await event_hub.publish("media", _media_payload(state))
        return state
    except CONTROL_ERRORS as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/media/sessions")
def get_media_sessions() -> dict:
    try:
        return controller.get_media_sessions()
    except MediaControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/media/sessions/control")
async def control_media_session(request: MediaSessionRequest) -> dict:
    try:
        sessions = await asyncio.to_thread(
            controller.control_media_session,
            request.player,
            request.action,
        )
        media_state = await asyncio.to_thread(controller.get_media_state)
        await event_hub.publish("media", media_state)
        return sessions
    except MediaControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/brightness")
async def control_brightness(request: BrightnessRequest) -> dict:
    try:
        state = await asyncio.to_thread(
            controller.change_brightness,
            request.action,
        )
        await event_hub.publish("brightness", _brightness_payload(state))
        return state
    except CONTROL_ERRORS as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/audio-routing")
def get_audio_routing() -> dict:
    try:
        return audio_routing.get_state()
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


async def _publish_audio_routing(action, *args) -> dict:
    state = await asyncio.to_thread(action, *args)
    await event_hub.publish("audio-routing", state)
    return state


@router.post("/audio-routing/default")
async def set_default_output(request: OutputRequest) -> dict:
    try:
        return await _publish_audio_routing(
            audio_routing.set_default,
            request.name,
        )
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/audio-routing/force")
async def force_audio_output(request: OutputRequest) -> dict:
    try:
        return await _publish_audio_routing(
            audio_routing.force_all,
            request.name,
        )
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/audio-routing/stream")
async def move_audio_stream(request: StreamOutputRequest) -> dict:
    try:
        return await _publish_audio_routing(
            audio_routing.move_stream,
            request.stream_index,
            request.name,
        )
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/audio-routing/stream/volume")
async def set_stream_volume(request: StreamVolumeRequest) -> dict:
    try:
        return await _publish_audio_routing(
            audio_routing.set_stream_volume,
            request.stream_index,
            request.volume,
        )
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/audio-routing/stream/mute")
async def toggle_stream_mute(request: StreamMuteRequest) -> dict:
    try:
        return await _publish_audio_routing(
            audio_routing.toggle_stream_mute,
            request.stream_index,
        )
    except AudioRoutingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
