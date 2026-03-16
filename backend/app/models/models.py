import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ─── Enums ────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


# ─── User ────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    tasks: Mapped[list["TranslationTask"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    glossaries: Mapped[list["GlossarySet"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    models: Mapped[list["CustomModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ─── Translation Task ────────────────────────────────────

class TranslationTask(Base):
    __tablename__ = "translation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.pending, nullable=False, index=True)

    # file info
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    output_mono_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_dual_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # translation params
    lang_in: Mapped[str] = mapped_column(String(16), nullable=False)
    lang_out: Mapped[str] = mapped_column(String(16), nullable=False)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("custom_models.id"), nullable=True)
    glossary_id: Mapped[int | None] = mapped_column(ForeignKey("glossary_sets.id"), nullable=True)
    pages: Mapped[str | None] = mapped_column(String(256), nullable=True)
    extra_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # translation options
    no_dual: Mapped[bool] = mapped_column(Boolean, default=False)
    no_mono: Mapped[bool] = mapped_column(Boolean, default=False)
    use_alternating_pages_dual: Mapped[bool] = mapped_column(Boolean, default=False)
    enhance_compatibility: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_workaround: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_translation: Mapped[bool] = mapped_column(Boolean, default=False)
    custom_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # progress & timing
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    progress_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # queue position
    queue_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # relationships
    user: Mapped["User"] = relationship(back_populates="tasks")
    model: Mapped["CustomModel | None"] = relationship()
    glossary: Mapped["GlossarySet | None"] = relationship()


# ─── Glossary ────────────────────────────────────────────

class GlossarySet(Base):
    __tablename__ = "glossary_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # relationships
    user: Mapped["User"] = relationship(back_populates="glossaries")
    entries: Mapped[list["GlossaryEntry"]] = relationship(back_populates="glossary_set", cascade="all, delete-orphan")


class GlossaryEntry(Base):
    __tablename__ = "glossary_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    glossary_set_id: Mapped[int] = mapped_column(ForeignKey("glossary_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    target: Mapped[str] = mapped_column(String(512), nullable=False)
    target_language: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # relationships
    glossary_set: Mapped["GlossarySet"] = relationship(back_populates="entries")


# ─── Custom Model ────────────────────────────────────────

class CustomModel(Base):
    __tablename__ = "custom_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_name: Mapped[str] = mapped_column(String(256), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    api_key: Mapped[str] = mapped_column(String(512), nullable=False)
    extra_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # advanced options
    send_temperature: Mapped[bool] = mapped_column(Boolean, default=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    reasoning: Mapped[str | None] = mapped_column(String(32), nullable=True)
    disable_thinking: Mapped[bool] = mapped_column(Boolean, default=False)
    enable_json_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # relationships
    user: Mapped["User"] = relationship(back_populates="models")
