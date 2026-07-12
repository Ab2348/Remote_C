import hashlib
import os
from dataclasses import dataclass
from pathlib import Path


class WallpaperError(RuntimeError):
    pass


@dataclass(frozen=True)
class WallpaperAsset:
    path: Path
    media_type: str
    revision: str


class HydeWallpaperService:
    MAX_FILE_SIZE = 20 * 1024 * 1024
    CANDIDATES = ("wall.thmb", "wall.set")

    def __init__(self, cache_dir: Path | None = None) -> None:
        cache_home = Path(
            os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
        )
        self.cache_dir = cache_dir or cache_home / "hyde"

    def get_state(self) -> dict:
        try:
            asset = self.get_asset()
        except WallpaperError:
            return {
                "available": False,
                "revision": None,
                "url": None,
            }

        return {
            "available": True,
            "revision": asset.revision,
            "url": f"/api/wallpaper/current?v={asset.revision}",
        }

    def get_asset(self, expected_revision: str | None = None) -> WallpaperAsset:
        for candidate_name in self.CANDIDATES:
            asset = self._read_candidate(self.cache_dir / candidate_name)

            if asset is None:
                continue

            if expected_revision and asset.revision != expected_revision:
                raise WallpaperError("El wallpaper cambió antes de poder cargarlo")

            return asset

        raise WallpaperError("HyDE no tiene un wallpaper disponible")

    def _read_candidate(self, candidate: Path) -> WallpaperAsset | None:
        try:
            path = candidate.resolve(strict=True)
            stat = path.stat()
        except (FileNotFoundError, OSError):
            return None

        if not path.is_file() or not 0 < stat.st_size <= self.MAX_FILE_SIZE:
            return None

        media_type = self._detect_media_type(path)
        if media_type is None:
            return None

        fingerprint = "\0".join(
            (
                str(path),
                str(stat.st_dev),
                str(stat.st_ino),
                str(stat.st_size),
                str(stat.st_mtime_ns),
            )
        )
        revision = hashlib.blake2s(
            fingerprint.encode(),
            digest_size=10,
        ).hexdigest()
        return WallpaperAsset(path, media_type, revision)

    @staticmethod
    def _detect_media_type(path: Path) -> str | None:
        try:
            with path.open("rb") as image:
                header = image.read(16)
        except OSError:
            return None

        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if header.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return "image/webp"

        return None


wallpaper = HydeWallpaperService()
