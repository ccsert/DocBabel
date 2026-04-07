import os
import uuid
import json
import hashlib
import tempfile
import zipfile
from typing import cast
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from app.models.models import User, TranslationTask, TaskStatus, GlossarySet, GlossaryEntry, CustomModel, UserRole
from app.schemas.schemas import BatchDownloadRequest, BatchTaskCreateOut, TaskCreate, TaskOut, TaskListOut, GlossarySetOut
from app.services.queue import translation_queue

router = APIRouter(prefix="/tasks", tags=["翻译任务"])

MAX_BATCH_UPLOAD_FILES = 20


def _compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _compute_model_config_hash(payload: dict) -> str:
    stable_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def _stringify_error_detail(detail: object, default: str = "处理失败") -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message:
            return message
        return json.dumps(detail, ensure_ascii=False)
    return default


async def _build_effective_model_hash_payload(
    db: AsyncSession,
    current_user: User,
    model_id: int | None,
    glossary_id: int | None,
    task_extra_body: dict | None,
    custom_system_prompt: str | None,
    auto_extract_glossary: bool,
    pages: str | None,
    no_dual: bool,
    no_mono: bool,
    use_alternating_pages_dual: bool,
    enhance_compatibility: bool,
    ocr_workaround: bool,
    skip_translation: bool,
) -> tuple[dict, int | None]:
    if not model_id:
        raise HTTPException(status_code=400, detail="必须选择一个已配置的模型")

    glossary_fingerprint = None
    if glossary_id:
        glossary_result = await db.execute(
            select(GlossarySet).where(
                GlossarySet.id == glossary_id,
                or_(GlossarySet.user_id == current_user.id, GlossarySet.is_collaborative.is_(True)),
            )
        )
        glossary = glossary_result.scalar_one_or_none()
        if not glossary:
            raise HTTPException(status_code=404, detail="术语表不存在")
        glossary_fingerprint = {
            "id": glossary.id,
            "updated_at": glossary.updated_at.isoformat() if glossary.updated_at else None,
        }

    result = await db.execute(
        select(CustomModel)
        .join(User, User.id == CustomModel.user_id)
        .where(
            CustomModel.id == model_id,
            User.role == UserRole.admin,
        )
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    merged_extra_body = dict(model.extra_body or {})
    if task_extra_body:
        merged_extra_body.update(task_extra_body)

    return {
        "model_name": model.model_name,
        "base_url": model.base_url,
        "send_temperature": model.send_temperature,
        "temperature": model.temperature,
        "reasoning": model.reasoning,
        "disable_thinking": model.disable_thinking,
        "enable_json_mode": model.enable_json_mode,
        "extra_body": merged_extra_body,
        "glossary": glossary_fingerprint,
        "custom_system_prompt": custom_system_prompt,
        "auto_extract_glossary": auto_extract_glossary,
        "pages": pages,
        "no_dual": no_dual,
        "no_mono": no_mono,
        "use_alternating_pages_dual": use_alternating_pages_dual,
        "enhance_compatibility": enhance_compatibility,
        "ocr_workaround": ocr_workaround,
        "skip_translation": skip_translation,
    }, model.id


async def _parse_extra_body(extra_body: str | None) -> dict | None:
    if not extra_body:
        return None
    try:
        return json.loads(extra_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="extra_body 必须为有效的 JSON") from exc


async def _validate_pdf_upload(filename: str, content: bytes):
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    try:
        import fitz
        with fitz.open(stream=content, filetype="pdf") as doc:
            meta = doc.metadata
            if meta:
                producer = meta.get("producer", "") or ""
                if "BabelDOC" in producer and "Translation_generated_by_AI" in producer:
                    raise HTTPException(
                        status_code=400,
                        detail="该 PDF 已由 BabelDOC 翻译生成，无法对已翻译的文件再次翻译。请上传原始 PDF 文件。",
                    )
    except HTTPException:
        raise
    except Exception:
        pass


async def _find_duplicate_task(
    db: AsyncSession,
    *,
    file_hash: str,
    model_config_hash: str,
    lang_in: str,
    lang_out: str,
) -> TranslationTask | None:
    duplicate_result = await db.execute(
        select(TranslationTask)
        .where(
            TranslationTask.status == TaskStatus.completed,
            TranslationTask.file_hash == file_hash,
            TranslationTask.model_config_hash == model_config_hash,
            TranslationTask.lang_in == lang_in,
            TranslationTask.lang_out == lang_out,
            or_(
                TranslationTask.output_mono_filename.is_not(None),
                TranslationTask.output_dual_filename.is_not(None),
            ),
        )
        .order_by(TranslationTask.completed_at.desc(), TranslationTask.id.desc())
        .limit(1)
    )
    return duplicate_result.scalars().first()


async def _ensure_queue_capacity(db: AsyncSession):
    queued_count = (await db.execute(
        select(func.count(TranslationTask.id)).where(
            TranslationTask.status.in_([TaskStatus.pending, TaskStatus.queued])
        )
    )).scalar()
    if (queued_count or 0) >= settings.MAX_QUEUE_SIZE:
        raise HTTPException(status_code=429, detail="翻译队列已满，请稍后再试")


async def _prepare_task_creation(
    db: AsyncSession,
    *,
    current_user: User,
    file: UploadFile,
    lang_in: str,
    lang_out: str,
    model_id: int,
    glossary_id: int | None,
    pages: str | None,
    extra_body: str | None,
    no_dual: bool,
    no_mono: bool,
    use_alternating_pages_dual: bool,
    enhance_compatibility: bool,
    ocr_workaround: bool,
    skip_translation: bool,
    custom_system_prompt: str | None,
    auto_extract_glossary: bool,
) -> dict[str, object]:
    filename = file.filename or ""
    content = await file.read()
    await _validate_pdf_upload(filename, content)
    extra_body_dict = await _parse_extra_body(extra_body)

    file_hash = _compute_file_hash(content)
    model_hash_payload, normalized_model_id = await _build_effective_model_hash_payload(
        db,
        current_user,
        model_id,
        glossary_id,
        extra_body_dict,
        custom_system_prompt,
        auto_extract_glossary,
        pages,
        no_dual,
        no_mono,
        use_alternating_pages_dual,
        enhance_compatibility,
        ocr_workaround,
        skip_translation,
    )
    model_config_hash = _compute_model_config_hash(model_hash_payload)
    duplicate_task = await _find_duplicate_task(
        db,
        file_hash=file_hash,
        model_config_hash=model_config_hash,
        lang_in=lang_in,
        lang_out=lang_out,
    )

    return {
        "filename": filename,
        "content": content,
        "extra_body_dict": extra_body_dict,
        "file_hash": file_hash,
        "model_config_hash": model_config_hash,
        "normalized_model_id": normalized_model_id,
        "duplicate_task": duplicate_task,
    }


async def _create_pending_task(
    db: AsyncSession,
    *,
    current_user: User,
    filename: str,
    content: bytes,
    file_hash: str,
    model_config_hash: str,
    normalized_model_id: int | None,
    lang_in: str,
    lang_out: str,
    glossary_id: int | None,
    pages: str | None,
    extra_body_dict: dict | None,
    no_dual: bool,
    no_mono: bool,
    use_alternating_pages_dual: bool,
    enhance_compatibility: bool,
    ocr_workaround: bool,
    skip_translation: bool,
    custom_system_prompt: str | None,
    auto_extract_glossary: bool,
) -> TranslationTask:
    await _ensure_queue_capacity(db)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = Path(filename).suffix
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(settings.UPLOAD_DIR, stored_name)
    async with aiofiles.open(stored_path, "wb") as handle:
        await handle.write(content)

    task = TranslationTask(
        user_id=current_user.id,
        original_filename=filename,
        stored_filename=stored_name,
        file_hash=file_hash,
        model_config_hash=model_config_hash,
        lang_in=lang_in,
        lang_out=lang_out,
        model_id=normalized_model_id,
        glossary_id=glossary_id,
        pages=pages,
        extra_body=extra_body_dict,
        no_dual=no_dual,
        no_mono=no_mono,
        use_alternating_pages_dual=use_alternating_pages_dual,
        enhance_compatibility=enhance_compatibility,
        ocr_workaround=ocr_workaround,
        skip_translation=skip_translation,
        custom_system_prompt=custom_system_prompt,
        auto_extract_glossary=auto_extract_glossary,
        status=TaskStatus.pending,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await translation_queue.enqueue(task.id)
    return task


async def _create_reused_task(
    db: AsyncSession,
    *,
    current_user: User,
    duplicate_task: TranslationTask,
    filename: str,
    file_hash: str,
    model_config_hash: str,
    normalized_model_id: int | None,
    lang_in: str,
    lang_out: str,
    glossary_id: int | None,
    pages: str | None,
    extra_body_dict: dict | None,
    no_dual: bool,
    no_mono: bool,
    use_alternating_pages_dual: bool,
    enhance_compatibility: bool,
    ocr_workaround: bool,
    skip_translation: bool,
    custom_system_prompt: str | None,
    auto_extract_glossary: bool,
) -> TranslationTask:
    reused_task = TranslationTask(
        user_id=current_user.id,
        original_filename=filename,
        stored_filename=duplicate_task.stored_filename,
        file_hash=file_hash,
        model_config_hash=model_config_hash,
        lang_in=lang_in,
        lang_out=lang_out,
        model_id=normalized_model_id,
        glossary_id=glossary_id,
        pages=pages,
        extra_body=extra_body_dict,
        no_dual=no_dual,
        no_mono=no_mono,
        use_alternating_pages_dual=use_alternating_pages_dual,
        enhance_compatibility=enhance_compatibility,
        ocr_workaround=ocr_workaround,
        skip_translation=skip_translation,
        custom_system_prompt=custom_system_prompt,
        auto_extract_glossary=auto_extract_glossary,
        extracted_glossary_data=duplicate_task.extracted_glossary_data,
        status=TaskStatus.completed,
        progress=100.0,
        progress_message="复用已有译文",
        token_usage=duplicate_task.token_usage,
        output_mono_filename=duplicate_task.output_mono_filename,
        output_dual_filename=duplicate_task.output_dual_filename,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(reused_task)
    await db.commit()
    await db.refresh(reused_task)
    return reused_task


def _build_unique_archive_name(used_names: set[str], filename: str) -> str:
    candidate = filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    index = 2
    while candidate in used_names:
        candidate = f"{stem}_{index}{suffix}"
        index += 1
    used_names.add(candidate)
    return candidate


def _cleanup_temp_file(path: str):
    if os.path.exists(path):
        os.remove(path)


def _normalize_date_param(value: str | None, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        if len(value) == 10:
            if end_of_day:
                parsed = parsed + timedelta(days=1)
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


async def _remove_file_if_orphan(db: AsyncSession, filename: str | None, base_dir: str, current_task_id: int):
    if not filename:
        return
    ref_count = (
        await db.execute(
            select(func.count(TranslationTask.id)).where(
                TranslationTask.id != current_task_id,
                or_(
                    TranslationTask.stored_filename == filename,
                    TranslationTask.output_mono_filename == filename,
                    TranslationTask.output_dual_filename == filename,
                ),
            )
        )
    ).scalar()
    if ref_count == 0:
        filepath = os.path.join(base_dir, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    file: UploadFile = File(...),
    lang_in: str = Form("en"),
    lang_out: str = Form("zh"),
    model_id: int = Form(...),
    glossary_id: int | None = Form(None),
    pages: str | None = Form(None),
    extra_body: str | None = Form(None),
    no_dual: bool = Form(False),
    no_mono: bool = Form(False),
    use_alternating_pages_dual: bool = Form(False),
    enhance_compatibility: bool = Form(False),
    ocr_workaround: bool = Form(False),
    skip_translation: bool = Form(False),
    custom_system_prompt: str | None = Form(None),
    auto_extract_glossary: bool = Form(False),
    reuse_existing: bool = Form(False),
    force_regenerate: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prepared = await _prepare_task_creation(
        db,
        current_user=current_user,
        file=file,
        lang_in=lang_in,
        lang_out=lang_out,
        model_id=model_id,
        glossary_id=glossary_id,
        pages=pages,
        extra_body=extra_body,
        no_dual=no_dual,
        no_mono=no_mono,
        use_alternating_pages_dual=use_alternating_pages_dual,
        enhance_compatibility=enhance_compatibility,
        ocr_workaround=ocr_workaround,
        skip_translation=skip_translation,
        custom_system_prompt=custom_system_prompt,
        auto_extract_glossary=auto_extract_glossary,
    )
    filename = cast(str, prepared["filename"])
    content = cast(bytes, prepared["content"])
    extra_body_dict = cast(dict | None, prepared["extra_body_dict"])
    file_hash = cast(str, prepared["file_hash"])
    model_config_hash = cast(str, prepared["model_config_hash"])
    normalized_model_id = cast(int | None, prepared["normalized_model_id"])
    duplicate_task = cast(TranslationTask | None, prepared["duplicate_task"])

    if duplicate_task and not reuse_existing and not force_regenerate:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_translation_exists",
                "message": "检测到该 PDF 在相同模型配置下已有译文，可直接复用下载。",
                "existing_task_id": duplicate_task.id,
                "has_mono": bool(duplicate_task.output_mono_filename),
                "has_dual": bool(duplicate_task.output_dual_filename),
            },
        )

    if duplicate_task and force_regenerate:
        raise HTTPException(
            status_code=400,
            detail="该 PDF 在当前翻译配置下已有译文。若要重新生成，请修改任一翻译配置后重试，例如术语表、页码、提示词、extra_body、输出选项或模型参数。",
        )

    if duplicate_task and reuse_existing:
        return await _create_reused_task(
            db,
            current_user=current_user,
            duplicate_task=duplicate_task,
            filename=filename,
            file_hash=file_hash,
            model_config_hash=model_config_hash,
            normalized_model_id=normalized_model_id,
            lang_in=lang_in,
            lang_out=lang_out,
            glossary_id=glossary_id,
            pages=pages,
            extra_body_dict=extra_body_dict,
            no_dual=no_dual,
            no_mono=no_mono,
            use_alternating_pages_dual=use_alternating_pages_dual,
            enhance_compatibility=enhance_compatibility,
            ocr_workaround=ocr_workaround,
            skip_translation=skip_translation,
            custom_system_prompt=custom_system_prompt,
            auto_extract_glossary=auto_extract_glossary,
        )
    return await _create_pending_task(
        db,
        current_user=current_user,
        filename=filename,
        content=content,
        file_hash=file_hash,
        model_config_hash=model_config_hash,
        normalized_model_id=normalized_model_id,
        lang_in=lang_in,
        lang_out=lang_out,
        glossary_id=glossary_id,
        pages=pages,
        extra_body_dict=extra_body_dict,
        no_dual=no_dual,
        no_mono=no_mono,
        use_alternating_pages_dual=use_alternating_pages_dual,
        enhance_compatibility=enhance_compatibility,
        ocr_workaround=ocr_workaround,
        skip_translation=skip_translation,
        custom_system_prompt=custom_system_prompt,
        auto_extract_glossary=auto_extract_glossary,
    )


@router.post("/batch", response_model=BatchTaskCreateOut, status_code=201)
async def create_tasks_batch(
    files: list[UploadFile] = File(...),
    lang_in: str = Form("en"),
    lang_out: str = Form("zh"),
    model_id: int = Form(...),
    glossary_id: int | None = Form(None),
    pages: str | None = Form(None),
    extra_body: str | None = Form(None),
    no_dual: bool = Form(False),
    no_mono: bool = Form(False),
    use_alternating_pages_dual: bool = Form(False),
    enhance_compatibility: bool = Form(False),
    ocr_workaround: bool = Form(False),
    skip_translation: bool = Form(False),
    custom_system_prompt: str | None = Form(None),
    auto_extract_glossary: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="请至少选择一个 PDF 文件")
    if len(files) > MAX_BATCH_UPLOAD_FILES:
        raise HTTPException(status_code=400, detail=f"单次最多上传 {MAX_BATCH_UPLOAD_FILES} 个文件")

    created_tasks: list[TranslationTask] = []
    skipped_items: list[dict[str, object]] = []
    failed_items: list[dict[str, str]] = []

    for upload in files:
        filename = upload.filename or "未命名文件"
        try:
            prepared = await _prepare_task_creation(
                db,
                current_user=current_user,
                file=upload,
                lang_in=lang_in,
                lang_out=lang_out,
                model_id=model_id,
                glossary_id=glossary_id,
                pages=pages,
                extra_body=extra_body,
                no_dual=no_dual,
                no_mono=no_mono,
                use_alternating_pages_dual=use_alternating_pages_dual,
                enhance_compatibility=enhance_compatibility,
                ocr_workaround=ocr_workaround,
                skip_translation=skip_translation,
                custom_system_prompt=custom_system_prompt,
                auto_extract_glossary=auto_extract_glossary,
            )
            duplicate_task = cast(TranslationTask | None, prepared["duplicate_task"])
            if duplicate_task:
                skipped_items.append({
                    "filename": cast(str, prepared["filename"]),
                    "existing_task_id": duplicate_task.id,
                    "has_mono": bool(duplicate_task.output_mono_filename),
                    "has_dual": bool(duplicate_task.output_dual_filename),
                    "reason": "检测到相同翻译配置下已有译文，已跳过",
                })
                continue

            task = await _create_pending_task(
                db,
                current_user=current_user,
                filename=cast(str, prepared["filename"]),
                content=cast(bytes, prepared["content"]),
                file_hash=cast(str, prepared["file_hash"]),
                model_config_hash=cast(str, prepared["model_config_hash"]),
                normalized_model_id=cast(int | None, prepared["normalized_model_id"]),
                lang_in=lang_in,
                lang_out=lang_out,
                glossary_id=glossary_id,
                pages=pages,
                extra_body_dict=cast(dict | None, prepared["extra_body_dict"]),
                no_dual=no_dual,
                no_mono=no_mono,
                use_alternating_pages_dual=use_alternating_pages_dual,
                enhance_compatibility=enhance_compatibility,
                ocr_workaround=ocr_workaround,
                skip_translation=skip_translation,
                custom_system_prompt=custom_system_prompt,
                auto_extract_glossary=auto_extract_glossary,
            )
            created_tasks.append(task)
        except HTTPException as exc:
            failed_items.append({
                "filename": filename,
                "reason": _stringify_error_detail(exc.detail),
            })

    return BatchTaskCreateOut(
        created_tasks=cast(list[TaskOut], created_tasks),
        skipped_items=skipped_items,
        failed_items=failed_items,
        total_files=len(files),
        created_count=len(created_tasks),
        skipped_count=len(skipped_items),
        failed_count=len(failed_items),
    )


@router.get("", response_model=TaskListOut)
async def list_my_tasks(
    status: str | None = None,
    q: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(TranslationTask).where(TranslationTask.user_id == current_user.id)
    count_query = select(func.count(TranslationTask.id)).where(TranslationTask.user_id == current_user.id)

    start_dt = _normalize_date_param(start_date)
    end_dt = _normalize_date_param(end_date, end_of_day=True)
    if start_dt is None and end_dt is None:
        start_dt = datetime.now(timezone.utc) - timedelta(days=3)

    if status:
        query = query.where(TranslationTask.status == TaskStatus(status))
        count_query = count_query.where(TranslationTask.status == TaskStatus(status))

    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(TranslationTask.original_filename.ilike(pattern))
        count_query = count_query.where(TranslationTask.original_filename.ilike(pattern))

    if start_dt is not None:
        query = query.where(TranslationTask.created_at >= start_dt)
        count_query = count_query.where(TranslationTask.created_at >= start_dt)

    if end_dt is not None:
        query = query.where(TranslationTask.created_at < end_dt)
        count_query = count_query.where(TranslationTask.created_at < end_dt)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(TranslationTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    tasks = list(result.scalars().all())
    return TaskListOut(tasks=cast(list[TaskOut], tasks), total=total)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TranslationTask).where(
            TranslationTask.id == task_id,
            TranslationTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TranslationTask).where(
            TranslationTask.id == task_id,
            TranslationTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in (TaskStatus.completed, TaskStatus.cancelled):
        raise HTTPException(status_code=400, detail="任务已完成或已取消")
    task.status = TaskStatus.cancelled
    await db.commit()
    return {"detail": "已取消"}


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TranslationTask).where(
            TranslationTask.id == task_id,
            TranslationTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in (TaskStatus.running, TaskStatus.queued, TaskStatus.pending):
        raise HTTPException(status_code=400, detail="请先取消运行中的任务，再删除")

    stored_filename = task.stored_filename
    mono_filename = task.output_mono_filename
    dual_filename = task.output_dual_filename

    await db.delete(task)
    await db.commit()

    await _remove_file_if_orphan(db, stored_filename, settings.UPLOAD_DIR, task_id)
    await _remove_file_if_orphan(db, mono_filename, settings.OUTPUT_DIR, task_id)
    await _remove_file_if_orphan(db, dual_filename, settings.OUTPUT_DIR, task_id)
    return {"detail": "已删除"}


class SaveGlossaryRequest(BaseModel):
    name: str
    description: str | None = None


@router.post("/{task_id}/save-glossary", response_model=GlossarySetOut, status_code=201)
async def save_extracted_glossary(
    task_id: int,
    data: SaveGlossaryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """将任务自动提取的术语保存为新的术语表。"""
    result = await db.execute(
        select(TranslationTask).where(
            TranslationTask.id == task_id,
            TranslationTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.extracted_glossary_data:
        raise HTTPException(status_code=400, detail="该任务没有自动提取的术语")

    gs = GlossarySet(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
    )
    for term in task.extracted_glossary_data:
        gs.entries.append(GlossaryEntry(
            source=term["source"],
            target=term["target"],
        ))
    db.add(gs)
    await db.commit()
    result2 = await db.execute(
        select(GlossarySet)
        .options(selectinload(GlossarySet.entries))
        .where(GlossarySet.id == gs.id)
    )
    return result2.scalar_one()


@router.get("/{task_id}/download/{file_type}")
async def download_result(
    task_id: int,
    file_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TranslationTask).where(
            TranslationTask.id == task_id,
            TranslationTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != TaskStatus.completed:
        raise HTTPException(status_code=400, detail="任务尚未完成")

    if file_type == "mono" and task.output_mono_filename:
        filepath = os.path.join(settings.OUTPUT_DIR, task.output_mono_filename)
    elif file_type == "dual" and task.output_dual_filename:
        filepath = os.path.join(settings.OUTPUT_DIR, task.output_dual_filename)
    else:
        raise HTTPException(status_code=404, detail="文件不存在")

    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="文件不存在")

    stem = Path(task.original_filename).stem
    suffix = "mono" if file_type == "mono" else "dual"
    download_name = f"{stem}_{suffix}.pdf"
    return FileResponse(filepath, filename=download_name, media_type="application/pdf")


@router.post("/batch-download")
async def download_batch_results(
    data: BatchDownloadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task_ids = list(dict.fromkeys(data.task_ids))
    result = await db.execute(
        select(TranslationTask).where(
            TranslationTask.id.in_(task_ids),
            TranslationTask.user_id == current_user.id,
        )
    )
    tasks = {task.id: task for task in result.scalars().all()}

    invalid_items: list[dict[str, object]] = []
    ready_items: list[tuple[TranslationTask, str, str]] = []
    suffix = "mono" if data.file_type == "mono" else "dual"

    for task_id in task_ids:
        task = tasks.get(task_id)
        if not task:
            invalid_items.append({"task_id": task_id, "reason": "任务不存在或无权限"})
            continue
        if task.status != TaskStatus.completed:
            invalid_items.append({"task_id": task_id, "reason": "任务尚未完成，无法批量下载"})
            continue

        output_name = task.output_mono_filename if data.file_type == "mono" else task.output_dual_filename
        if not output_name:
            invalid_items.append({"task_id": task_id, "reason": "该任务没有对应类型的输出文件"})
            continue

        filepath = os.path.join(settings.OUTPUT_DIR, output_name)
        if not os.path.isfile(filepath):
            invalid_items.append({"task_id": task_id, "reason": "输出文件不存在"})
            continue

        archive_name = f"{Path(task.original_filename).stem}_{suffix}.pdf"
        ready_items.append((task, filepath, archive_name))

    if invalid_items:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "batch_download_invalid_tasks",
                "message": "部分任务无法批量下载，请调整选择后重试。",
                "invalid_items": invalid_items,
            },
        )

    if not ready_items:
        raise HTTPException(status_code=400, detail="没有可下载的任务")

    tmp = tempfile.NamedTemporaryFile(prefix="babeldoc_batch_", suffix=".zip", delete=False)
    tmp.close()
    used_names: set[str] = set()
    with zipfile.ZipFile(tmp.name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for _, filepath, archive_name in ready_items:
            archive.write(filepath, arcname=_build_unique_archive_name(used_names, archive_name))

    download_name = f"batch_download_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    return FileResponse(
        tmp.name,
        filename=download_name,
        media_type="application/zip",
        background=BackgroundTask(_cleanup_temp_file, tmp.name),
    )
