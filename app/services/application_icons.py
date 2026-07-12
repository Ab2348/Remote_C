import mimetypes
import os
import re
from functools import lru_cache
from pathlib import Path


class ApplicationIconError(RuntimeError):
    pass


class ApplicationIconService:
    SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
    SIZES = (
        "scalable",
        "512x512",
        "256x256",
        "128x128",
        "96x96",
        "64x64",
        "48x48",
        "32x32",
    )
    EXTENSIONS = ("svg", "png", "xpm")
    ALIASES = {
        "brave": ("brave-browser", "brave"),
        "brave-browser": ("brave-browser", "brave"),
        "chromium": ("chromium", "chromium-browser"),
        "discord": ("discord", "com.discordapp.Discord"),
        "firefox": ("firefox", "org.mozilla.firefox"),
        "spotify": ("spotify", "spotify-client", "com.spotify.Client"),
        "spotify-client": ("spotify", "spotify-client", "com.spotify.Client"),
        "steam": ("steam", "com.valvesoftware.Steam"),
        "vlc": ("vlc", "org.videolan.VLC"),
    }

    def __init__(
        self,
        icon_roots: tuple[Path, ...] | None = None,
        pixmap_roots: tuple[Path, ...] | None = None,
        custom_roots: tuple[Path, ...] | None = None,
    ) -> None:
        data_home = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")
        )
        self.icon_roots = icon_roots if icon_roots is not None else (
            data_home / "icons/hicolor",
            data_home / "flatpak/exports/share/icons/hicolor",
            Path("/usr/share/icons/hicolor"),
            Path("/var/lib/flatpak/exports/share/icons/hicolor"),
        )
        self.pixmap_roots = pixmap_roots if pixmap_roots is not None else (
            data_home / "pixmaps",
            Path("/usr/share/pixmaps"),
        )
        self.custom_roots = custom_roots if custom_roots is not None else (
            Path(__file__).resolve().parents[1] / "static/application-icons",
        )

    @lru_cache(maxsize=128)
    def resolve(self, icon_name: str) -> tuple[Path, str]:
        requested = icon_name.strip()

        if not requested or not self.SAFE_NAME.fullmatch(requested):
            raise ApplicationIconError("El nombre del icono no es válido")

        candidates = self._names_for(requested)

        for path in self._candidate_paths(candidates):
            media_type, _ = mimetypes.guess_type(path.name)

            if path.is_file() and media_type and media_type.startswith("image/"):
                return path.resolve(), media_type

        raise ApplicationIconError("No hay un icono instalado para esta aplicación")

    def _names_for(self, requested: str) -> tuple[str, ...]:
        normalized = requested.casefold()
        aliases = self.ALIASES.get(normalized, ())
        return tuple(dict.fromkeys((requested, normalized, *aliases)))

    def _candidate_paths(self, names: tuple[str, ...]):
        for root in self.icon_roots:
            for size in self.SIZES:
                for name in names:
                    for extension in self.EXTENSIONS:
                        yield root / size / "apps" / f"{name}.{extension}"

        for root in self.pixmap_roots:
            for name in names:
                for extension in self.EXTENSIONS:
                    yield root / f"{name}.{extension}"

        for root in self.custom_roots:
            for name in names:
                for extension in self.EXTENSIONS:
                    yield root / f"{name}.{extension}"


application_icons = ApplicationIconService()
