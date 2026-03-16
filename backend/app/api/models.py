import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
import httpx
import openai
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.models import User, CustomModel, UserRole
from app.schemas.schemas import CustomModelCreate, CustomModelUpdate, CustomModelOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["自定义模型"])


@router.get("", response_model=list[CustomModelOut])
async def list_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomModel)
        .join(User, User.id == CustomModel.user_id)
        .where(User.role == UserRole.admin)
        .order_by(CustomModel.updated_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=CustomModelOut, status_code=201)
async def create_model(
    data: CustomModelCreate,
    current_user: User = Depends(require_admin),
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
        select(CustomModel)
        .join(User, User.id == CustomModel.user_id)
        .where(CustomModel.id == model_id, User.role == UserRole.admin)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return model


@router.patch("/{model_id}", response_model=CustomModelOut)
async def update_model(
    model_id: int,
    data: CustomModelUpdate,
    current_user: User = Depends(require_admin),
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
    current_user: User = Depends(require_admin),
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


class ModelTestRequest(BaseModel):
    model_name: str
    base_url: str | None = None
    api_key: str
    extra_body: dict | None = None
    send_temperature: bool = True
    reasoning: str | None = None
    disable_thinking: bool = False


@router.post("/test")
async def test_model(
    data: ModelTestRequest,
    current_user: User = Depends(require_admin),
):
    """发送一个简单的翻译请求来测试模型配置是否可用。"""
    def _do_test():
        extra_body = {}
        if data.reasoning:
            extra_body["reasoning"] = {"effort": data.reasoning}
        if data.disable_thinking:
            extra_body["chat_template_kwargs"] = {"enable_thinking": False}
        if data.extra_body:
            extra_body.update(data.extra_body)

        client = openai.OpenAI(
            base_url=data.base_url or None,
            api_key=data.api_key,
            http_client=httpx.Client(timeout=30),
        )

        options = {}
        if data.send_temperature:
            options["temperature"] = 0

        response = client.chat.completions.create(
            model=data.model_name,
            **options,
            messages=[
                {"role": "system", "content": "You are a professional,authentic machine translation engine."},
                {"role": "user", "content": ";; Translate the following text into Chinese, output translation ONLY.\n\nHello, world!"},
            ],
            extra_body=extra_body if extra_body else None,
        )

        result_text = response.choices[0].message.content.strip()
        usage = None
        if response.usage:
            usage = {
                "total_tokens": response.usage.total_tokens,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        return result_text, usage, response.model

    try:
        loop = asyncio.get_event_loop()
        result_text, usage, model_id = await loop.run_in_executor(None, _do_test)
        return {
            "success": True,
            "result": result_text,
            "model": model_id,
            "usage": usage,
        }
    except Exception as e:
        logger.warning(f"Model test failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/{model_id}/test")
async def test_existing_model(
    model_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """测试已保存的模型配置。"""
    result = await db.execute(
        select(CustomModel).where(CustomModel.id == model_id, CustomModel.user_id == current_user.id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    req = ModelTestRequest(
        model_name=model.model_name,
        base_url=model.base_url,
        api_key=model.api_key,
        extra_body=model.extra_body,
        send_temperature=model.send_temperature,
        reasoning=model.reasoning,
        disable_thinking=model.disable_thinking,
    )
    return await test_model(req, current_user)
