from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import get_password_hash
from app.models.models import User, UserRole, TranslationTask, TaskStatus
from app.schemas.schemas import UserOut, UserUpdate, TaskOut, TaskListOut

router = APIRouter(prefix="/admin", tags=["管理员"], dependencies=[Depends(require_admin)])


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
    total = total_result.scalar()

    query = query.order_by(TranslationTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    tasks = result.scalars().all()
    return TaskListOut(tasks=tasks, total=total)


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
