import json
import os
import subprocess
from dataclasses import dataclass


class AudioRoutingError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioSink:
    index: int
    name: str
    label: str
    state: str
    active: bool


@dataclass(frozen=True)
class AudioStream:
    index: int
    sink: int
    application: str
    media: str
    binary: str
    pid: str
    volume: int
    muted: bool


class PactlAudioRoutingService:
    def get_state(self) -> dict:
        sinks = self._get_sinks()
        streams = self._get_streams()
        sink_by_index = {sink.index: sink for sink in sinks}

        return {
            "outputs": [
                {
                    "name": sink.name,
                    "label": sink.label,
                    "state": sink.state.casefold(),
                    "active": sink.active,
                }
                for sink in sinks
            ],
            "streams": [
                {
                    "index": stream.index,
                    "application": stream.application,
                    "media": stream.media,
                    "binary": stream.binary,
                    "pid": stream.pid,
                    "volume": stream.volume,
                    "muted": stream.muted,
                    "output_name": (
                        sink_by_index[stream.sink].name
                        if stream.sink in sink_by_index
                        else None
                    ),
                    "output_label": (
                        sink_by_index[stream.sink].label
                        if stream.sink in sink_by_index
                        else "Salida desconocida"
                    ),
                }
                for stream in streams
            ],
        }

    def set_default(self, output_name: str) -> dict:
        sink = self._find_sink(output_name)
        self._run("set-default-sink", sink.name)
        return self.get_state()

    def force_all(self, output_name: str) -> dict:
        sink = self._find_sink(output_name)
        streams = self._get_streams()

        self._run("set-default-sink", sink.name)

        failed: list[int] = []

        for stream in streams:
            try:
                self._run(
                    "move-sink-input",
                    str(stream.index),
                    sink.name,
                )
            except AudioRoutingError:
                failed.append(stream.index)

        if failed:
            indexes = ", ".join(str(index) for index in failed)
            raise AudioRoutingError(
                f"No se pudieron mover los flujos: {indexes}"
            )

        return self.get_state()

    def move_stream(self, stream_index: int, output_name: str) -> dict:
        sink = self._find_sink(output_name)
        self._find_stream(stream_index)

        self._run(
            "move-sink-input",
            str(stream_index),
            sink.name,
        )

        return self.get_state()

    def set_stream_volume(
        self,
        stream_index: int,
        volume: int,
    ) -> dict:
        self._find_stream(stream_index)

        if not 0 <= volume <= 100:
            raise AudioRoutingError(
                "El volumen debe estar entre 0 y 100"
            )

        self._run(
            "set-sink-input-volume",
            str(stream_index),
            f"{volume}%",
        )

        return self.get_state()

    def toggle_stream_mute(self, stream_index: int) -> dict:
        self._find_stream(stream_index)

        self._run(
            "set-sink-input-mute",
            str(stream_index),
            "toggle",
        )

        return self.get_state()

    def _find_stream(self, stream_index: int) -> AudioStream:
        for stream in self._get_streams():
            if stream.index == stream_index:
                return stream

        raise AudioRoutingError(
            "El flujo seleccionado ya no está disponible"
        )

    def _find_sink(self, output_name: str) -> AudioSink:
        for sink in self._get_sinks():
            if sink.name == output_name:
                return sink

        raise AudioRoutingError(
            "La salida seleccionada ya no está disponible"
        )

    def _get_sinks(self) -> list[AudioSink]:
        data = self._run_json("list", "sinks")
        default_name = self._run("get-default-sink").strip()
        sinks: list[AudioSink] = []

        for item in data:
            properties = item.get("properties") or {}
            name = item.get("name")

            if not isinstance(name, str):
                continue

            description = item.get("description")

            if not description or description == "(null)":
                description = (
                    properties.get("device.description")
                    or properties.get("node.nick")
                    or name
                )

            sinks.append(
                AudioSink(
                    index=int(item["index"]),
                    name=name,
                    label=str(description),
                    state=str(item.get("state") or "unknown"),
                    active=name == default_name,
                )
            )

        return sorted(sinks, key=lambda sink: sink.label.casefold())

    def _get_streams(self) -> list[AudioStream]:
        data = self._run_json("list", "sink-inputs")
        streams: list[AudioStream] = []

        for item in data:
            properties = item.get("properties") or {}
            volume_data = item.get("volume") or {}
            channel_values = [
                int(channel["value"])
                for channel in volume_data.values()
                if isinstance(channel, dict) and "value" in channel
            ]
            volume = (
                round(
                    sum(channel_values)
                    / len(channel_values)
                    / 65536
                    * 100
                )
                if channel_values
                else 0
            )

            streams.append(
                AudioStream(
                    index=int(item["index"]),
                    sink=int(item["sink"]),
                    application=str(
                        properties.get("application.name")
                        or properties.get("application.process.binary")
                        or "Aplicación"
                    ),
                    media=str(properties.get("media.name") or "Audio"),
                    binary=str(
                        properties.get("application.process.binary") or ""
                    ),
                    pid=str(
                        properties.get("application.process.id") or ""
                    ),
                    volume=volume,
                    muted=bool(item.get("mute", False)),
                )
            )

        return sorted(streams, key=lambda stream: stream.index)

    def _run_json(self, *arguments: str) -> list:
        output = self._run("-f", "json", *arguments)

        try:
            value = json.loads(output)
        except json.JSONDecodeError as error:
            raise AudioRoutingError(
                "pactl devolvió información JSON inválida"
            ) from error

        if not isinstance(value, list):
            raise AudioRoutingError(
                "pactl devolvió una estructura inesperada"
            )

        return value

    @staticmethod
    def _run(*arguments: str) -> str:
        environment = os.environ.copy()
        environment["LC_ALL"] = "C"

        try:
            result = subprocess.run(
                ["pactl", *arguments],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                env=environment,
            )
        except FileNotFoundError as error:
            raise AudioRoutingError(
                "pactl no está disponible"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise AudioRoutingError(
                "pactl tardó demasiado en responder"
            ) from error

        if result.returncode != 0:
            message = result.stderr.strip() or "pactl devolvió un error"
            raise AudioRoutingError(message)

        return result.stdout.strip()


audio_routing = PactlAudioRoutingService()
