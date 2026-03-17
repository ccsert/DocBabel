from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.models import User, UserRole
from app.schemas.schemas import (
    LoginRequest,
    RegisterRequest,
    Token,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # check duplicates
    result = await db.execute(
        select(User).where((User.username == req.username) | (User.email == req.email))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    # If no active admin exists, the next registered user becomes admin as a recovery path.
    admin_result = await db.execute(
        select(User.id)
        .where(User.role == UserRole.admin, User.is_active.is_(True))
        .limit(1)
    )
    role = UserRole.admin if admin_result.scalar_one_or_none() is None else UserRole.user

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=get_password_hash(req.password),
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")
    token = create_access_token(user.username)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
