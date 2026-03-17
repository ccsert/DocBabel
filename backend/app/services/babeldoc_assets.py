"""Helpers for preparing and validating BabelDOC assets in web backend."""

from __future__ import annotations

import threading
from pathlib import Path

from babeldoc.assets.assets import generate_all_assets_file_list
from babeldoc.assets.assets import restore_offline_assets_package_async
from babeldoc.assets.assets import verify_file
from babeldoc.const import get_cache_file_path

_OFFLINE_ASSETS_READY = False
_OFFLINE_ASSETS_LOCK = threading.Lock()


def ensure_offline_assets_ready(force: bool = False) -> None:
    """Validate that all BabelDOC runtime assets exist in local cache.

    In offline mode, the backend should fail fast with a clear error instead of
    letting BabelDOC attempt network downloads during translation.
    """
    global _OFFLINE_ASSETS_READY

    with _OFFLINE_ASSETS_LOCK:
        if _OFFLINE_ASSETS_READY and not force:
            return

        file_list = generate_all_assets_file_list()
        missing_files: list[str] = []

        for file_type, file_descs in file_list.items():
            for file_desc in file_descs:
                file_name = file_desc["name"]
                sha3_256 = file_desc["sha3_256"]
                file_path = get_cache_file_path(file_name, file_type)
                if not verify_file(file_path, sha3_256):
                    missing_files.append(f"{file_type}/{file_name}")

        if missing_files:
            preview = ", ".join(missing_files[:5])
            remainder = len(missing_files) - min(len(missing_files), 5)
            if remainder > 0:
                preview = f"{preview} and {remainder} more"
            raise RuntimeError(
                "BabelDOC offline mode is enabled, but required local assets are missing. "
                f"Missing: {preview}. "
                "Preload assets online first, or provide an offline assets package via "
                "BABELDOC_OFFLINE_ASSETS_PACKAGE."
            )

        _OFFLINE_ASSETS_READY = True


async def restore_offline_assets_package(package_path: str) -> None:
    """Restore a BabelDOC offline assets package into the local cache."""
    package = Path(package_path).expanduser()
    if not package.exists():
        raise RuntimeError(f"Configured offline assets package not found: {package}")
    await restore_offline_assets_package_async(package)
    ensure_offline_assets_ready(force=True)