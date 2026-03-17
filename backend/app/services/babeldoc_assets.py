"""Helpers for preparing and validating BabelDOC assets in web backend."""

from __future__ import annotations

import asyncio
import threading
import zipfile
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from babeldoc.assets.assets import async_warmup
from babeldoc.assets.assets import generate_all_assets_file_list
from babeldoc.assets.assets import get_offline_assets_tag
from babeldoc.assets.assets import restore_offline_assets_package_async
from babeldoc.assets.assets import verify_file
from babeldoc.const import get_cache_file_path

from app.core.config import settings

_OFFLINE_ASSETS_READY = False
_OFFLINE_ASSETS_LOCK = threading.Lock()
_OFFLINE_ASSETS_EXPORT_LOCK = threading.Lock()
_OFFLINE_ASSETS_EXPORT_TASK: asyncio.Task | None = None
_OFFLINE_ASSETS_EXPORT_STATE = {
    "status": "idle",
    "step": None,
    "message": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "output_path": None,
}

OFFLINE_ASSET_PROFILES: dict[str, set[str]] = {
    "full": {"models", "fonts", "cmap", "tiktoken"},
    "core": {"models", "fonts", "tiktoken"},
    "minimal": {"models", "tiktoken"},
}

OFFLINE_ASSET_PROFILE_DESCRIPTIONS = {
    "full": "检查全部 BabelDOC 运行资产，最适合严格离线场景。",
    "core": "检查模型、字体和 tiktoken 缓存，适合较轻量的离线预检。",
    "minimal": "仅检查模型和 tiktoken 缓存，启动前校验最轻，但不能保证所有 PDF 处理资源完整。",
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def get_offline_assets_export_dir() -> Path:
    return Path(settings.BABELDOC_OFFLINE_EXPORT_DIR).expanduser()


def get_offline_assets_package_path(output_directory: Path | None = None) -> Path:
    target_directory = output_directory or get_offline_assets_export_dir()
    offline_assets_tag = get_offline_assets_tag(generate_all_assets_file_list())
    return target_directory / f"offline_assets_{offline_assets_tag}.zip"


def _build_package_metadata(path: Path | None) -> dict | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    stat = path.stat()
    return {
        "path": str(path),
        "filename": path.name,
        "size_bytes": stat.st_size,
        "modified_at": _serialize_datetime(datetime.fromtimestamp(stat.st_mtime, UTC)),
        "download_path": "/api/admin/offline-assets/export/download",
    }


def _find_latest_offline_assets_package(output_directory: Path | None = None) -> Path | None:
    target_directory = output_directory or get_offline_assets_export_dir()
    if not target_directory.exists():
        return None
    packages = sorted(
        target_directory.glob("offline_assets_*.zip"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return packages[0] if packages else None


def _set_offline_assets_export_state(**updates) -> None:
    with _OFFLINE_ASSETS_EXPORT_LOCK:
        _OFFLINE_ASSETS_EXPORT_STATE.update(updates)


def get_offline_assets_export_status() -> dict:
    latest_package = _build_package_metadata(_find_latest_offline_assets_package())
    with _OFFLINE_ASSETS_EXPORT_LOCK:
        status = deepcopy(_OFFLINE_ASSETS_EXPORT_STATE)

    return {
        "status": status["status"],
        "step": status["step"],
        "message": status["message"],
        "started_at": _serialize_datetime(status["started_at"]),
        "finished_at": _serialize_datetime(status["finished_at"]),
        "error": status["error"],
        "output_path": status["output_path"],
        "output_dir": str(get_offline_assets_export_dir()),
        "latest_package": latest_package,
    }


def get_latest_offline_assets_package_path() -> Path | None:
    return _find_latest_offline_assets_package()


def _write_offline_assets_package(output_path: Path) -> None:
    file_list = generate_all_assets_file_list()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    with zipfile.ZipFile(
        temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zipf:
        for file_type, file_descs in file_list.items():
            for file_desc in file_descs:
                file_name = file_desc["name"]
                sha3_256 = file_desc["sha3_256"]
                file_path = get_cache_file_path(file_name, file_type)
                if not verify_file(file_path, sha3_256):
                    raise RuntimeError(f"Asset file is missing or corrupted: {file_type}/{file_name}")

                with file_path.open("rb") as asset_file:
                    zipf.writestr(f"{file_type}/{file_name}", asset_file.read())
    temp_path.replace(output_path)


async def _run_offline_assets_export() -> None:
    output_path = get_offline_assets_package_path()
    try:
        _set_offline_assets_export_state(
            status="running",
            step="warming",
            message="正在预热并下载离线资源",
            started_at=_utc_now(),
            finished_at=None,
            error=None,
            output_path=str(output_path),
        )
        await async_warmup()
        _set_offline_assets_export_state(
            step="packaging",
            message="正在打包离线资源",
        )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_offline_assets_package, output_path)
        get_offline_assets_status(force=True)
        _set_offline_assets_export_state(
            status="completed",
            step="completed",
            message="离线资源包生成完成",
            finished_at=_utc_now(),
            error=None,
            output_path=str(output_path),
        )
    except Exception as exc:
        _set_offline_assets_export_state(
            status="failed",
            step="failed",
            message="离线资源包生成失败",
            finished_at=_utc_now(),
            error=str(exc),
            output_path=str(output_path),
        )
        raise


async def start_offline_assets_export() -> dict:
    global _OFFLINE_ASSETS_EXPORT_TASK

    with _OFFLINE_ASSETS_EXPORT_LOCK:
        if _OFFLINE_ASSETS_EXPORT_TASK is not None and not _OFFLINE_ASSETS_EXPORT_TASK.done():
            raise RuntimeError("离线资源导出任务正在执行中")
        _OFFLINE_ASSETS_EXPORT_TASK = asyncio.create_task(_run_offline_assets_export())

    return get_offline_assets_export_status()


def get_offline_asset_profile() -> str:
    profile = (settings.BABELDOC_OFFLINE_ASSET_PROFILE or "full").strip().lower()
    if profile not in OFFLINE_ASSET_PROFILES:
        raise RuntimeError(
            "Invalid BABELDOC_OFFLINE_ASSET_PROFILE: "
            f"{settings.BABELDOC_OFFLINE_ASSET_PROFILE}. "
            f"Supported values: {', '.join(sorted(OFFLINE_ASSET_PROFILES))}."
        )
    return profile


def get_profiled_asset_file_list(profile: str | None = None) -> dict[str, list[dict[str, str]]]:
    selected_profile = profile or get_offline_asset_profile()
    enabled_types = OFFLINE_ASSET_PROFILES[selected_profile]
    all_files = generate_all_assets_file_list()
    return {
        file_type: file_descs
        for file_type, file_descs in all_files.items()
        if file_type in enabled_types
    }


class OfflineAssetsMissingError(RuntimeError):
    """Raised when offline mode is enabled but local BabelDOC assets are incomplete."""

    def __init__(self, missing_files: list[str], total_files: int, present_files: int, profile: str):
        self.missing_files = missing_files
        self.total_files = total_files
        self.present_files = present_files
        self.profile = profile

        preview = ", ".join(missing_files[:5])
        remainder = len(missing_files) - min(len(missing_files), 5)
        if remainder > 0:
            preview = f"{preview} and {remainder} more"

        super().__init__(
            "BabelDOC offline mode is enabled, but required local assets are missing. "
            f"Profile: {profile}. "
            f"Missing: {preview}. "
            "Preload assets online first, or provide an offline assets package via "
            "BABELDOC_OFFLINE_ASSETS_PACKAGE."
        )


def get_offline_assets_status(force: bool = False) -> dict:
    """Return structured status for all BabelDOC runtime assets."""
    global _OFFLINE_ASSETS_READY

    with _OFFLINE_ASSETS_LOCK:
        if force:
            _OFFLINE_ASSETS_READY = False

        profile = get_offline_asset_profile()
        file_list = get_profiled_asset_file_list(profile)
        missing_files: list[str] = []
        present_files = 0
        by_type: dict[str, dict[str, object]] = {}

        for file_type, file_descs in file_list.items():
            total = len(file_descs)
            type_missing: list[str] = []
            type_present = 0

            for file_desc in file_descs:
                file_name = file_desc["name"]
                sha3_256 = file_desc["sha3_256"]
                file_path = get_cache_file_path(file_name, file_type)
                file_key = f"{file_type}/{file_name}"
                if verify_file(file_path, sha3_256):
                    present_files += 1
                    type_present += 1
                else:
                    missing_files.append(file_key)
                    type_missing.append(file_name)

            by_type[file_type] = {
                "total": total,
                "present": type_present,
                "missing": total - type_present,
                "ready": total == type_present,
                "missing_files": type_missing,
            }

        total_files = sum(len(file_descs) for file_descs in file_list.values())
        ready = not missing_files
        _OFFLINE_ASSETS_READY = ready

        return {
            "profile": profile,
            "profile_description": OFFLINE_ASSET_PROFILE_DESCRIPTIONS[profile],
            "ready": ready,
            "total_files": total_files,
            "present_files": present_files,
            "missing_files": len(missing_files),
            "missing_file_paths": missing_files,
            "by_type": by_type,
        }


def ensure_offline_assets_ready(force: bool = False) -> None:
    """Validate that all BabelDOC runtime assets exist in local cache.

    In offline mode, the backend should fail fast with a clear error instead of
    letting BabelDOC attempt network downloads during translation.
    """
    status = get_offline_assets_status(force=force)
    if not status["ready"]:
        raise OfflineAssetsMissingError(
            missing_files=status["missing_file_paths"],
            total_files=status["total_files"],
            present_files=status["present_files"],
            profile=status["profile"],
        )


async def restore_offline_assets_package(package_path: str) -> None:
    """Restore a BabelDOC offline assets package into the local cache."""
    package = Path(package_path).expanduser()
    if not package.exists():
        raise RuntimeError(f"Configured offline assets package not found: {package}")
    await restore_offline_assets_package_async(package)
    ensure_offline_assets_ready(force=True)