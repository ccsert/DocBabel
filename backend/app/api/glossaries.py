from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import User, GlossarySet, GlossaryEntry
from app.schemas.schemas import (
    GlossarySetCreate,
    GlossarySetUpdate,
    GlossarySetOut,
    GlossaryEntryIn,
    GlossaryEntryOut,
)

router = APIRouter(prefix="/glossaries", tags=["术语表"])


@router.get("", response_model=list[GlossarySetOut])
async def list_glossaries(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GlossarySet)
        .options(selectinload(GlossarySet.entries))
        .where(GlossarySet.user_id == current_user.id)
        .order_by(GlossarySet.updated_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=GlossarySetOut, status_code=201)
async def create_glossary(
    data: GlossarySetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gs = GlossarySet(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
    )
    for e in data.entries:
        gs.entries.append(GlossaryEntry(source=e.source, target=e.target, target_language=e.target_language))
    db.add(gs)
    await db.commit()
    # reload with entries
    result = await db.execute(
        select(GlossarySet).options(selectinload(GlossarySet.entries)).where(GlossarySet.id == gs.id)
    )
    return result.scalar_one()


@router.get("/{glossary_id}", response_model=GlossarySetOut)
async def get_glossary(
    glossary_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GlossarySet)
        .options(selectinload(GlossarySet.entries))
        .where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    gs = result.scalar_one_or_none()
    if not gs:
        raise HTTPException(status_code=404, detail="术语表不存在")
    return gs


@router.patch("/{glossary_id}", response_model=GlossarySetOut)
async def update_glossary(
    glossary_id: int,
    data: GlossarySetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GlossarySet)
        .options(selectinload(GlossarySet.entries))
        .where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    gs = result.scalar_one_or_none()
    if not gs:
        raise HTTPException(status_code=404, detail="术语表不存在")
    if data.name is not None:
        gs.name = data.name
    if data.description is not None:
        gs.description = data.description
    await db.commit()
    await db.refresh(gs)
    return gs


@router.delete("/{glossary_id}")
async def delete_glossary(
    glossary_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GlossarySet).where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    gs = result.scalar_one_or_none()
    if not gs:
        raise HTTPException(status_code=404, detail="术语表不存在")
    await db.delete(gs)
    await db.commit()
    return {"detail": "已删除"}


# ─── Entry management ────────────────────────────────────

@router.post("/{glossary_id}/entries", response_model=GlossaryEntryOut, status_code=201)
async def add_entry(
    glossary_id: int,
    data: GlossaryEntryIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GlossarySet).where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="术语表不存在")

    entry = GlossaryEntry(glossary_set_id=glossary_id, source=data.source, target=data.target, target_language=data.target_language)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{glossary_id}/entries/{entry_id}")
async def delete_entry(
    glossary_id: int,
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GlossaryEntry).where(
            GlossaryEntry.id == entry_id,
            GlossaryEntry.glossary_set_id == glossary_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="词条不存在")
    # verify ownership
    gs_result = await db.execute(
        select(GlossarySet).where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    if not gs_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="无权操作")
    await db.delete(entry)
    await db.commit()
    return {"detail": "已删除"}
