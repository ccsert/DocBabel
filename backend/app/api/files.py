from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import TaskStatus, TranslationTask, User
from app.schemas.schemas import FileLibraryItemOut, FileLibraryListOut

router = APIRouter(prefix="/files", tags=["文件库"])


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


@router.get("", response_model=FileLibraryListOut)
async def list_files(
    q: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(TranslationTask).where(
        TranslationTask.user_id == current_user.id,
        TranslationTask.status == TaskStatus.completed,
        or_(
            TranslationTask.output_mono_filename.is_not(None),
            TranslationTask.output_dual_filename.is_not(None),
        ),
    )

    start_dt = _normalize_date_param(start_date)
    end_dt = _normalize_date_param(end_date, end_of_day=True)
    if q:
        query = query.where(TranslationTask.original_filename.ilike(f"%{q.strip()}%"))
    if start_dt is not None:
        query = query.where(TranslationTask.created_at >= start_dt)
    if end_dt is not None:
        query = query.where(TranslationTask.created_at < end_dt)

    query = query.order_by(TranslationTask.completed_at.desc(), TranslationTask.id.desc())
    result = await db.execute(query)
    tasks = result.scalars().all()

    files_by_hash: dict[str, FileLibraryItemOut] = {}
    for task in tasks:
        file_hash = task.file_hash or f"legacy-{task.id}"
        existing = files_by_hash.get(file_hash)
        if existing is None:
            files_by_hash[file_hash] = FileLibraryItemOut(
                file_hash=file_hash,
                original_filename=task.original_filename,
                latest_task_id=task.id,
                latest_created_at=task.created_at,
                latest_completed_at=task.completed_at,
                latest_duration_seconds=task.duration_seconds,
                task_count=1,
                output_mono_filename=task.output_mono_filename,
                output_dual_filename=task.output_dual_filename,
            )
        else:
            existing.task_count += 1

    files = list(files_by_hash.values())
    return FileLibraryListOut(files=files, total=len(files))
