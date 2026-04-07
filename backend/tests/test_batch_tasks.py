import io
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import tasks as tasks_api
from app.schemas.schemas import BatchDownloadRequest


class FakeScalarListResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


def make_user(user_id: int = 1):
    return SimpleNamespace(id=user_id)


def make_task(task_id: int, filename: str, *, status: str = "completed", output_mono_filename: str | None = "mono.pdf"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=task_id,
        user_id=1,
        status=status,
        original_filename=filename,
        lang_in="en",
        lang_out="zh",
        model_id=1,
        glossary_id=None,
        pages=None,
        extra_body=None,
        no_dual=False,
        no_mono=False,
        use_alternating_pages_dual=False,
        enhance_compatibility=False,
        ocr_workaround=False,
        skip_translation=False,
        custom_system_prompt=None,
        progress=0.0,
        progress_message=None,
        error_message=None,
        token_usage=None,
        duration_seconds=None,
        queue_position=None,
        output_mono_filename=output_mono_filename,
        output_dual_filename=None,
        auto_extract_glossary=False,
        extracted_glossary_data=None,
        created_at=now,
        started_at=None,
        completed_at=now,
    )


@pytest.mark.asyncio
async def test_create_tasks_batch_skips_duplicates_and_creates_new_task(monkeypatch):
    duplicate_task = make_task(88, "duplicate.pdf", output_mono_filename="duplicate_mono.pdf")
    prepared_items = [
        {
            "filename": "duplicate.pdf",
            "content": b"dup",
            "extra_body_dict": None,
            "file_hash": "hash-a",
            "model_config_hash": "cfg-a",
            "normalized_model_id": 1,
            "duplicate_task": duplicate_task,
        },
        {
            "filename": "fresh.pdf",
            "content": b"fresh",
            "extra_body_dict": None,
            "file_hash": "hash-b",
            "model_config_hash": "cfg-b",
            "normalized_model_id": 1,
            "duplicate_task": None,
        },
    ]
    created_task = make_task(101, "fresh.pdf")

    monkeypatch.setattr(tasks_api, "_prepare_task_creation", AsyncMock(side_effect=prepared_items))
    monkeypatch.setattr(tasks_api, "_create_pending_task", AsyncMock(return_value=created_task))

    result = await tasks_api.create_tasks_batch(
        files=[
            UploadFile(filename="duplicate.pdf", file=io.BytesIO(b"dup")),
            UploadFile(filename="fresh.pdf", file=io.BytesIO(b"fresh")),
        ],
        model_id=1,
        current_user=make_user(),
        db=AsyncMock(),
    )

    assert result.total_files == 2
    assert result.created_count == 1
    assert result.skipped_count == 1
    assert result.failed_count == 0
    assert result.created_tasks[0].id == 101
    assert result.skipped_items[0].existing_task_id == 88


@pytest.mark.asyncio
async def test_download_batch_results_returns_zip_and_cleans_up(tmp_path, monkeypatch):
    mono_a = tmp_path / "mono_a.pdf"
    mono_b = tmp_path / "mono_b.pdf"
    mono_a.write_bytes(b"pdf-a")
    mono_b.write_bytes(b"pdf-b")

    task_a = make_task(1, "report.pdf", output_mono_filename=mono_a.name)
    task_b = make_task(2, "report.pdf", output_mono_filename=mono_b.name)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=FakeScalarListResult([task_a, task_b]))

    monkeypatch.setattr(tasks_api.settings, "OUTPUT_DIR", str(tmp_path))

    response = await tasks_api.download_batch_results(
        BatchDownloadRequest(task_ids=[1, 2], file_type="mono"),
        current_user=make_user(),
        db=db,
    )

    assert response.media_type == "application/zip"
    assert os.path.exists(response.path)

    with zipfile.ZipFile(response.path) as archive:
        assert sorted(archive.namelist()) == ["report_mono.pdf", "report_mono_2.pdf"]

    await response.background()
    assert not os.path.exists(response.path)


@pytest.mark.asyncio
async def test_download_batch_results_rejects_unfinished_tasks(tmp_path, monkeypatch):
    running_task = make_task(3, "draft.pdf", status="running", output_mono_filename="draft.pdf")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=FakeScalarListResult([running_task]))

    monkeypatch.setattr(tasks_api.settings, "OUTPUT_DIR", str(tmp_path))

    with pytest.raises(HTTPException) as exc:
        await tasks_api.download_batch_results(
            BatchDownloadRequest(task_ids=[3], file_type="mono"),
            current_user=make_user(),
            db=db,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "batch_download_invalid_tasks"