from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.models import User, UserRole, TranslationTask, TaskStatus
from app.schemas.schemas import UserOut, UserUpdate, TaskListOut
from app.services.babeldoc_assets import get_latest_offline_assets_package_path
from app.services.babeldoc_assets import get_offline_assets_export_status
from app.services.babeldoc_assets import get_offline_assets_status
from app.services.babeldoc_assets import restore_offline_assets_package
from app.services.babeldoc_assets import start_offline_assets_export

router = APIRouter(prefix="/admin", tags=["管理员"], dependencies=[Depends(require_admin)])


def _build_offline_assets_response(force: bool = False) -> dict:
    status = get_offline_assets_status(force=force)
    return {
        "offline_mode": settings.BABELDOC_OFFLINE_MODE,
        "offline_assets_package_configured": bool(settings.BABELDOC_OFFLINE_ASSETS_PACKAGE),
        "export": get_offline_assets_export_status(),
        **status,
    }


async def _has_other_active_admin(db: AsyncSession, excluded_user_id: int) -> bool:
    result = await db.execute(
        select(User.id)
        .where(
            User.role == UserRole.admin,
            User.is_active.is_(True),
            User.id != excluded_user_id,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


# ─── User management ─────────────────────────────────────

@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, data: UserUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    next_role = UserRole(data.role) if data.role is not None else user.role
    next_is_active = data.is_active if data.is_active is not None else user.is_active

    if user.role == UserRole.admin and user.is_active and (next_role != UserRole.admin or not next_is_active):
        if not await _has_other_active_admin(db, user.id):
            raise HTTPException(status_code=400, detail="至少保留一个启用状态的管理员")

    if data.email is not None:
        user.email = data.email
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.role is not None:
        user.role = UserRole(data.role)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == UserRole.admin and user.is_active and not await _has_other_active_admin(db, user.id):
        raise HTTPException(status_code=400, detail="至少保留一个启用状态的管理员")
    await db.delete(user)
    await db.commit()
    return {"detail": "已删除"}


# ─── Task management ─────────────────────────────────────

@router.get("/tasks", response_model=TaskListOut)
async def list_all_tasks(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(TranslationTask)
    count_query = select(func.count(TranslationTask.id))

    if status:
        query = query.where(TranslationTask.status == TaskStatus(status))
        count_query = count_query.where(TranslationTask.status == TaskStatus(status))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(TranslationTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    tasks = list(result.scalars().all())
    return {"tasks": tasks, "total": total}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TranslationTask).where(TranslationTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in (TaskStatus.completed, TaskStatus.cancelled):
        raise HTTPException(status_code=400, detail="任务已完成或已取消")
    task.status = TaskStatus.cancelled
    await db.commit()
    return {"detail": "已取消"}


@router.get("/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    user_count = (await db.execute(select(func.count(User.id)))).scalar()
    task_count = (await db.execute(select(func.count(TranslationTask.id)))).scalar()
    running = (await db.execute(
        select(func.count(TranslationTask.id)).where(TranslationTask.status == TaskStatus.running)
    )).scalar()
    queued = (await db.execute(
        select(func.count(TranslationTask.id)).where(TranslationTask.status.in_([TaskStatus.pending, TaskStatus.queued]))
    )).scalar()
    return {
        "user_count": user_count,
        "task_count": task_count,
        "running_tasks": running,
        "queued_tasks": queued,
    }


@router.get("/offline-assets/status")
async def offline_assets_status():
    return _build_offline_assets_response()


@router.post("/offline-assets/check")
async def check_offline_assets():
    return _build_offline_assets_response(force=True)


@router.post("/offline-assets/restore")
async def restore_configured_offline_assets():
    if not settings.BABELDOC_OFFLINE_ASSETS_PACKAGE:
        raise HTTPException(status_code=400, detail="未配置 BABELDOC_OFFLINE_ASSETS_PACKAGE")
    await restore_offline_assets_package(settings.BABELDOC_OFFLINE_ASSETS_PACKAGE)
    return {
        "detail": "离线资源包恢复完成",
        **_build_offline_assets_response(force=True),
    }


@router.post("/offline-assets/export")
async def export_offline_assets():
    try:
        await start_offline_assets_export()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "detail": "离线资源导出任务已启动",
        **_build_offline_assets_response(),
    }


@router.get("/offline-assets/export/download")
async def download_offline_assets_export():
    package_path = get_latest_offline_assets_package_path()
    if package_path is None or not package_path.exists():
        raise HTTPException(status_code=404, detail="暂无可下载的离线资源包")
    return FileResponse(
        package_path,
        filename=package_path.name,
        media_type="application/zip",
    )
