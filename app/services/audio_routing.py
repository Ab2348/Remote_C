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
    icon_name: str
    media: str
    binary: str
    pid: str
    volume: int
    muted: bool
    corked: bool


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
            "applications": self._serialize_applications(
                streams,
                sink_by_index,
            ),
        }

    @staticmethod
    def _serialize_applications(
        streams: list[AudioStream],
        sink_by_index: dict[int, AudioSink],
    ) -> list[dict]:
        groups: dict[str, list[AudioStream]] = {}

        for stream in streams:
            identity = stream.binary or stream.application
            application_id = identity.strip().casefold()
            groups.setdefault(application_id, []).append(stream)

        applications: list[dict] = []

        for application_id, group in groups.items():
            output_indexes = {stream.sink for stream in group}
            output = (
                sink_by_index.get(next(iter(output_indexes)))
                if len(output_indexes) == 1
                else None
            )
            muted_count = sum(stream.muted for stream in group)
            playing = any(not stream.corked for stream in group)
            media_names = list(
                dict.fromkeys(stream.media for stream in group if stream.media)
            )

            applications.append(
                {
                    "id": application_id,
                    "application": group[0].application,
                    "icon_name": next(
                        (
                            stream.icon_name
                            for stream in group
                            if stream.icon_name
                        ),
                        group[0].binary,
                    ),
                    "binary": group[0].binary,
                    "pids": list(
                        dict.fromkeys(stream.pid for stream in group if stream.pid)
                    ),
                    "media": media_names,
                    "stream_indexes": [stream.index for stream in group],
                    "stream_count": len(group),
                    "volume": round(
                        sum(stream.volume for stream in group) / len(group)
                    ),
                    "mixed_volume": len({stream.volume for stream in group}) > 1,
                    "muted": muted_count == len(group),
                    "partially_muted": 0 < muted_count < len(group),
                    "playing": playing,
                    "playback_status": "playing" if playing else "paused",
                    "output_name": output.name if output else None,
                    "output_label": (
                        output.label
                        if output
                        else (
                            "Varias salidas"
                            if len(output_indexes) > 1
                            else "Salida desconocida"
                        )
                    ),
                }
            )

        return sorted(
            applications,
            key=lambda application: application["application"].casefold(),
        )

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
            raise AudioRoutingError(f"No se pudieron mover los flujos: {indexes}")

        return self.get_state()

    def move_stream(self, stream_index: int, output_name: str) -> dict:
        return self.move_streams([stream_index], output_name)

    def move_streams(
        self,
        stream_indexes: list[int],
        output_name: str,
    ) -> dict:
        sink = self._find_sink(output_name)
        streams = self._find_streams(stream_indexes)
        self._run_for_streams(
            streams,
            "move-sink-input",
            sink.name,
        )
        return self.get_state()

    def set_stream_volume(
        self,
        stream_index: int,
        volume: int,
    ) -> dict:
        return self.set_streams_volume([stream_index], volume)

    def set_streams_volume(
        self,
        stream_indexes: list[int],
        volume: int,
    ) -> dict:
        streams = self._find_streams(stream_indexes)

        if not 0 <= volume <= 100:
            raise AudioRoutingError("El volumen debe estar entre 0 y 100")

        self._run_for_streams(
            streams,
            "set-sink-input-volume",
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

    def set_streams_mute(
        self,
        stream_indexes: list[int],
        muted: bool,
    ) -> dict:
        streams = self._find_streams(stream_indexes)
        self._run_for_streams(
            streams,
            "set-sink-input-mute",
            "1" if muted else "0",
        )
        return self.get_state()

    def _run_for_streams(
        self,
        streams: list[AudioStream],
        command: str,
        value: str,
    ) -> None:
        failed: list[int] = []

        for stream in streams:
            try:
                self._run(command, str(stream.index), value)
            except AudioRoutingError:
                failed.append(stream.index)

        if failed:
            indexes = ", ".join(str(index) for index in failed)
            raise AudioRoutingError(f"No se pudieron actualizar los flujos: {indexes}")

    def _find_stream(self, stream_index: int) -> AudioStream:
        for stream in self._get_streams():
            if stream.index == stream_index:
                return stream

        raise AudioRoutingError("El flujo seleccionado ya no está disponible")

    def _find_streams(self, stream_indexes: list[int]) -> list[AudioStream]:
        requested = set(stream_indexes)
        streams = [
            stream for stream in self._get_streams() if stream.index in requested
        ]

        if not streams:
            raise AudioRoutingError(
                "La aplicación seleccionada ya no está reproduciendo audio"
            )

        return streams

    def _find_sink(self, output_name: str) -> AudioSink:
        for sink in self._get_sinks():
            if sink.name == output_name:
                return sink

        raise AudioRoutingError("La salida seleccionada ya no está disponible")

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
                round(sum(channel_values) / len(channel_values) / 65536 * 100)
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
                    icon_name=str(
                        properties.get("application.icon_name")
                        or properties.get("application.process.binary")
                        or ""
                    ),
                    media=str(properties.get("media.name") or "Audio"),
                    binary=str(properties.get("application.process.binary") or ""),
                    pid=str(properties.get("application.process.id") or ""),
                    volume=volume,
                    muted=bool(item.get("mute", False)),
                    corked=bool(item.get("corked", False)),
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
            raise AudioRoutingError("pactl devolvió una estructura inesperada")

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
            raise AudioRoutingError("pactl no está disponible") from error
        except subprocess.TimeoutExpired as error:
            raise AudioRoutingError("pactl tardó demasiado en responder") from error

        if result.returncode != 0:
            message = result.stderr.strip() or "pactl devolvió un error"
            raise AudioRoutingError(message)

        return result.stdout.strip()


audio_routing = PactlAudioRoutingService()
