import os
import uuid
import json
import hashlib
from typing import cast
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from app.models.models import User, TranslationTask, TaskStatus, GlossarySet, GlossaryEntry, CustomModel, UserRole
from app.schemas.schemas import TaskCreate, TaskOut, TaskListOut, GlossarySetOut
from app.services.queue import translation_queue

router = APIRouter(prefix="/tasks", tags=["翻译任务"])


def _compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _compute_model_config_hash(payload: dict) -> str:
    stable_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


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
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # parse extra_body JSON
    extra_body_dict = None
    if extra_body:
        try:
            extra_body_dict = json.loads(extra_body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="extra_body 必须为有效的 JSON")

    content = await file.read()
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
    duplicate_task = duplicate_result.scalars().first()

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

    # check queue size
    queued_count = (await db.execute(
        select(func.count(TranslationTask.id)).where(
            TranslationTask.status.in_([TaskStatus.pending, TaskStatus.queued])
        )
    )).scalar()
    if (queued_count or 0) >= settings.MAX_QUEUE_SIZE:
        raise HTTPException(status_code=429, detail="翻译队列已满，请稍后再试")

    # save uploaded file
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = Path(filename).suffix
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(settings.UPLOAD_DIR, stored_name)
    async with aiofiles.open(stored_path, "wb") as f:
        await f.write(content)

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

    # enqueue
    await translation_queue.enqueue(task.id)

    return task


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
