from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import User, CustomModel
from app.schemas.schemas import CustomModelCreate, CustomModelUpdate, CustomModelOut

router = APIRouter(prefix="/models", tags=["自定义模型"])


@router.get("", response_model=list[CustomModelOut])
async def list_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomModel)
        .where(CustomModel.user_id == current_user.id)
        .order_by(CustomModel.updated_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=CustomModelOut, status_code=201)
async def create_model(
    data: CustomModelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    model = CustomModel(
        user_id=current_user.id,
        name=data.name,
        model_name=data.model_name,
        base_url=data.base_url,
        api_key=data.api_key,
        extra_body=data.extra_body,
        send_temperature=data.send_temperature,
        temperature=data.temperature,
        reasoning=data.reasoning,
        disable_thinking=data.disable_thinking,
        enable_json_mode=data.enable_json_mode,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.get("/{model_id}", response_model=CustomModelOut)
async def get_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomModel).where(CustomModel.id == model_id, CustomModel.user_id == current_user.id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return model


@router.patch("/{model_id}", response_model=CustomModelOut)
async def update_model(
    model_id: int,
    data: CustomModelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomModel).where(CustomModel.id == model_id, CustomModel.user_id == current_user.id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(model, field, value)
    await db.commit()
    await db.refresh(model)
    return model


@router.delete("/{model_id}")
async def delete_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomModel).where(CustomModel.id == model_id, CustomModel.user_id == current_user.id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    await db.delete(model)
    await db.commit()
    return {"detail": "已删除"}
