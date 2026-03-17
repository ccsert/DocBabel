import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.admin import delete_user, update_user
from app.api.auth import register
from app.models.models import UserRole
from app.schemas.schemas import RegisterRequest, UserUpdate


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def make_user(*, user_id: int = 1, role: UserRole = UserRole.user, is_active: bool = True):
    return SimpleNamespace(
        id=user_id,
        username=f"user{user_id}",
        email=f"user{user_id}@example.com",
        hashed_password="hashed",
        role=role,
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_update_user_blocks_demoting_last_active_admin():
    user = make_user(role=UserRole.admin)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[FakeResult(user), FakeResult(None)])

    with pytest.raises(HTTPException) as exc:
        await update_user(user.id, UserUpdate(role="user"), db)

    assert exc.value.status_code == 400
    assert "至少保留一个启用状态的管理员" in exc.value.detail
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_user_blocks_deleting_last_active_admin():
    user = make_user(role=UserRole.admin)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[FakeResult(user), FakeResult(None)])

    with pytest.raises(HTTPException) as exc:
        await delete_user(user.id, db)

    assert exc.value.status_code == 400
    assert "至少保留一个启用状态的管理员" in exc.value.detail
    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_assigns_admin_when_no_active_admin_exists():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[FakeResult(None), FakeResult(None)])
    db.add = Mock()
    db.refresh = AsyncMock()

    user = await register(
        RegisterRequest(username="recovery", email="recovery@example.com", password="secret123"),
        db,
    )

    assert user.role == UserRole.admin
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_assigns_user_when_active_admin_exists():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[FakeResult(None), FakeResult(1)])
    db.add = Mock()
    db.refresh = AsyncMock()

    user = await register(
        RegisterRequest(username="normal", email="normal@example.com", password="secret123"),
        db,
    )

    assert user.role == UserRole.user