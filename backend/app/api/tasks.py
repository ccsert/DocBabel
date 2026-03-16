import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import User, TranslationTask, TaskStatus
from app.schemas.schemas import TaskCreate, TaskOut, TaskListOut
from app.services.queue import translation_queue

router = APIRouter(prefix="/tasks", tags=["翻译任务"])


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    file: UploadFile = File(...),
    lang_in: str = Form("en"),
    lang_out: str = Form("zh"),
    model_id: int | None = Form(None),
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # check queue size
    queued_count = (await db.execute(
        select(func.count(TranslationTask.id)).where(
            TranslationTask.status.in_([TaskStatus.pending, TaskStatus.queued])
        )
    )).scalar()
    if queued_count >= settings.MAX_QUEUE_SIZE:
        raise HTTPException(status_code=429, detail="翻译队列已满，请稍后再试")

    # save uploaded file
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = Path(file.filename).suffix
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(settings.UPLOAD_DIR, stored_name)
    async with aiofiles.open(stored_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # parse extra_body JSON
    import json
    extra_body_dict = None
    if extra_body:
        try:
            extra_body_dict = json.loads(extra_body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="extra_body 必须为有效的 JSON")

    task = TranslationTask(
        user_id=current_user.id,
        original_filename=file.filename,
        stored_filename=stored_name,
        lang_in=lang_in,
        lang_out=lang_out,
        model_id=model_id,
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
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(TranslationTask).where(TranslationTask.user_id == current_user.id)
    count_query = select(func.count(TranslationTask.id)).where(TranslationTask.user_id == current_user.id)

    if status:
        query = query.where(TranslationTask.status == TaskStatus(status))
        count_query = count_query.where(TranslationTask.status == TaskStatus(status))

    total = (await db.execute(count_query)).scalar()
    query = query.order_by(TranslationTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    tasks = result.scalars().all()
    return TaskListOut(tasks=tasks, total=total)


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
