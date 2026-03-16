import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import (
    User,
    GlossarySet,
    GlossaryEntry,
    GlossaryContribution,
    GlossaryContributionStatus,
)
from app.schemas.schemas import (
    GlossarySetCreate,
    GlossarySetUpdate,
    GlossarySetOut,
    GlossaryEntryIn,
    GlossaryEntryUpdate,
    GlossaryEntryOut,
    GlossaryContributionIn,
    GlossaryContributionOut,
    GlossaryContributionReviewIn,
)

router = APIRouter(prefix="/glossaries", tags=["术语表"])


async def _get_accessible_glossary(db: AsyncSession, glossary_id: int, current_user: User) -> GlossarySet | None:
    result = await db.execute(
        select(GlossarySet)
        .options(
            selectinload(GlossarySet.entries),
            selectinload(GlossarySet.contributions),
        )
        .where(
            GlossarySet.id == glossary_id,
            or_(GlossarySet.user_id == current_user.id, GlossarySet.is_collaborative.is_(True)),
        )
    )
    return result.scalar_one_or_none()


def _serialize_glossary(gs: GlossarySet, current_user: User) -> GlossarySetOut:
    is_owner = gs.user_id == current_user.id
    pending = []
    for contribution in gs.contributions:
        if contribution.status != GlossaryContributionStatus.pending:
            continue
        if is_owner or contribution.proposer_user_id == current_user.id:
            pending.append(GlossaryContributionOut.model_validate(contribution))

    return GlossarySetOut(
        id=gs.id,
        user_id=gs.user_id,
        name=gs.name,
        description=gs.description,
        is_collaborative=gs.is_collaborative,
        is_owner=is_owner,
        created_at=gs.created_at,
        updated_at=gs.updated_at,
        entries=[GlossaryEntryOut.model_validate(entry) for entry in gs.entries],
        pending_contributions=pending,
    )


@router.get("", response_model=list[GlossarySetOut])
async def list_glossaries(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GlossarySet)
        .options(
            selectinload(GlossarySet.entries),
            selectinload(GlossarySet.contributions),
        )
        .where(or_(GlossarySet.user_id == current_user.id, GlossarySet.is_collaborative.is_(True)))
        .order_by(GlossarySet.updated_at.desc())
    )
    glossaries = result.scalars().all()
    return [_serialize_glossary(gs, current_user) for gs in glossaries]


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
        is_collaborative=data.is_collaborative,
    )
    for e in data.entries:
        gs.entries.append(GlossaryEntry(source=e.source, target=e.target, target_language=e.target_language))
    db.add(gs)
    await db.commit()
    result = await db.execute(
        select(GlossarySet)
        .options(selectinload(GlossarySet.entries), selectinload(GlossarySet.contributions))
        .where(GlossarySet.id == gs.id)
    )
    return _serialize_glossary(result.scalar_one(), current_user)


@router.get("/{glossary_id}", response_model=GlossarySetOut)
async def get_glossary(
    glossary_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gs = await _get_accessible_glossary(db, glossary_id, current_user)
    if not gs:
        raise HTTPException(status_code=404, detail="术语表不存在")
    return _serialize_glossary(gs, current_user)


@router.patch("/{glossary_id}", response_model=GlossarySetOut)
async def update_glossary(
    glossary_id: int,
    data: GlossarySetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GlossarySet)
        .options(selectinload(GlossarySet.entries), selectinload(GlossarySet.contributions))
        .where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    gs = result.scalar_one_or_none()
    if not gs:
        raise HTTPException(status_code=404, detail="术语表不存在")
    if data.name is not None:
        gs.name = data.name
    if data.description is not None:
        gs.description = data.description
    if data.is_collaborative is not None:
        gs.is_collaborative = data.is_collaborative
    await db.commit()
    await db.refresh(gs)
    return _serialize_glossary(gs, current_user)


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


@router.post("/{glossary_id}/entries", status_code=201)
async def add_entry(
    glossary_id: int,
    data: GlossaryEntryIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gs = await _get_accessible_glossary(db, glossary_id, current_user)
    if not gs:
        raise HTTPException(status_code=404, detail="术语表不存在")

    if gs.user_id == current_user.id:
        entry = GlossaryEntry(glossary_set_id=glossary_id, source=data.source, target=data.target, target_language=data.target_language)
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return {
            "mode": "approved",
            "entry": GlossaryEntryOut.model_validate(entry).model_dump(),
        }

    if not gs.is_collaborative:
        raise HTTPException(status_code=403, detail="该术语表未开启共创")

    contribution = GlossaryContribution(
        glossary_set_id=glossary_id,
        proposer_user_id=current_user.id,
        source=data.source,
        target=data.target,
        target_language=data.target_language,
        status=GlossaryContributionStatus.pending,
    )
    db.add(contribution)
    await db.commit()
    await db.refresh(contribution)
    return {
        "mode": "pending",
        "contribution": GlossaryContributionOut.model_validate(contribution).model_dump(),
        "detail": "已提交共创词条，等待术语表创建者确认",
    }


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
    gs_result = await db.execute(
        select(GlossarySet).where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    if not gs_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="无权操作")
    await db.delete(entry)
    await db.commit()
    return {"detail": "已删除"}


@router.patch("/{glossary_id}/entries/{entry_id}", response_model=GlossaryEntryOut)
async def update_entry(
    glossary_id: int,
    entry_id: int,
    data: GlossaryEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gs_result = await db.execute(
        select(GlossarySet).where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    if not gs_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="无权操作")

    result = await db.execute(
        select(GlossaryEntry).where(
            GlossaryEntry.id == entry_id,
            GlossaryEntry.glossary_set_id == glossary_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="词条不存在")

    if data.source is not None:
        entry.source = data.source
    if data.target is not None:
        entry.target = data.target
    if data.target_language is not None:
        entry.target_language = data.target_language

    await db.commit()
    await db.refresh(entry)
    return entry


@router.post("/{glossary_id}/contributions", response_model=GlossaryContributionOut, status_code=201)
async def create_contribution(
    glossary_id: int,
    data: GlossaryContributionIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gs = await _get_accessible_glossary(db, glossary_id, current_user)
    if not gs:
        raise HTTPException(status_code=404, detail="术语表不存在")
    if not gs.is_collaborative or gs.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="该术语表无需通过共创提议添加")

    contribution = GlossaryContribution(
        glossary_set_id=glossary_id,
        proposer_user_id=current_user.id,
        source=data.source,
        target=data.target,
        target_language=data.target_language,
        status=GlossaryContributionStatus.pending,
    )
    db.add(contribution)
    await db.commit()
    await db.refresh(contribution)
    return contribution


@router.post("/{glossary_id}/contributions/{contribution_id}/approve", response_model=GlossaryContributionOut)
async def approve_contribution(
    glossary_id: int,
    contribution_id: int,
    data: GlossaryContributionReviewIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gs_result = await db.execute(
        select(GlossarySet).where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    if not gs_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="仅术语表创建者可审核")

    result = await db.execute(
        select(GlossaryContribution).where(
            GlossaryContribution.id == contribution_id,
            GlossaryContribution.glossary_set_id == glossary_id,
        )
    )
    contribution = result.scalar_one_or_none()
    if not contribution:
        raise HTTPException(status_code=404, detail="共创词条不存在")
    if contribution.status != GlossaryContributionStatus.pending:
        raise HTTPException(status_code=400, detail="该共创词条已审核")

    entry = GlossaryEntry(
        glossary_set_id=glossary_id,
        source=contribution.source,
        target=contribution.target,
        target_language=contribution.target_language,
    )
    db.add(entry)
    contribution.status = GlossaryContributionStatus.approved
    contribution.reviewer_user_id = current_user.id
    contribution.review_note = data.review_note
    contribution.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(contribution)
    return contribution


@router.post("/{glossary_id}/contributions/{contribution_id}/reject", response_model=GlossaryContributionOut)
async def reject_contribution(
    glossary_id: int,
    contribution_id: int,
    data: GlossaryContributionReviewIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gs_result = await db.execute(
        select(GlossarySet).where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    if not gs_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="仅术语表创建者可审核")

    result = await db.execute(
        select(GlossaryContribution).where(
            GlossaryContribution.id == contribution_id,
            GlossaryContribution.glossary_set_id == glossary_id,
        )
    )
    contribution = result.scalar_one_or_none()
    if not contribution:
        raise HTTPException(status_code=404, detail="共创词条不存在")
    if contribution.status != GlossaryContributionStatus.pending:
        raise HTTPException(status_code=400, detail="该共创词条已审核")

    contribution.status = GlossaryContributionStatus.rejected
    contribution.reviewer_user_id = current_user.id
    contribution.review_note = data.review_note
    contribution.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(contribution)
    return contribution


@router.post("/{glossary_id}/import", response_model=GlossarySetOut)
async def import_entries(
    glossary_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GlossarySet)
        .options(selectinload(GlossarySet.entries), selectinload(GlossarySet.contributions))
        .where(GlossarySet.id == glossary_id, GlossarySet.user_id == current_user.id)
    )
    gs = result.scalar_one_or_none()
    if not gs:
        raise HTTPException(status_code=404, detail="术语表不存在")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("gbk")

    dialect = csv.Sniffer().sniff(text[:2048], delimiters=",\t;")
    reader = csv.reader(io.StringIO(text), dialect)

    entries_added = 0
    for i, row in enumerate(reader):
        if len(row) < 2:
            continue
        source = row[0].strip()
        target = row[1].strip()
        target_lang = row[2].strip() if len(row) > 2 else None
        if i == 0 and source.lower() in ("source", "原文", "src"):
            continue
        if not source or not target:
            continue
        db.add(
            GlossaryEntry(
                glossary_set_id=glossary_id,
                source=source,
                target=target,
                target_language=target_lang or None,
            )
        )
        entries_added += 1

    if entries_added == 0:
        raise HTTPException(status_code=400, detail="文件中未找到有效词条，请检查格式")

    await db.commit()
    result = await db.execute(
        select(GlossarySet)
        .options(selectinload(GlossarySet.entries), selectinload(GlossarySet.contributions))
        .where(GlossarySet.id == glossary_id)
    )
    return _serialize_glossary(result.scalar_one(), current_user)
