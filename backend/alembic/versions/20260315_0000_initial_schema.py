"""initial schema

Revision ID: 20260315_0000
Revises:
Create Date: 2026-03-15 23:50:00
"""

from typing import Sequence

import alembic.op as op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260315_0000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    user_role_enum = postgresql.ENUM("user", "admin", name="userrole", create_type=False)
    task_status_enum = postgresql.ENUM(
        "pending",
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="taskstatus",
        create_type=False,
    )

    user_role_enum.create(op.get_bind(), checkfirst=True)
    task_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("hashed_password", sa.String(length=256), nullable=False),
        sa.Column("role", user_role_enum, nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "glossary_sets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_glossary_sets_user_id", "glossary_sets", ["user_id"], unique=False)

    op.create_table(
        "custom_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("model_name", sa.String(length=256), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("api_key", sa.String(length=512), nullable=False),
        sa.Column("extra_body", sa.JSON(), nullable=True),
        sa.Column("send_temperature", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.String(length=32), nullable=True),
        sa.Column("disable_thinking", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable_json_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_custom_models_user_id", "custom_models", ["user_id"], unique=False)

    op.create_table(
        "glossary_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "glossary_set_id",
            sa.Integer(),
            sa.ForeignKey("glossary_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=512), nullable=False),
        sa.Column("target", sa.String(length=512), nullable=False),
        sa.Column("target_language", sa.String(length=16), nullable=True),
    )
    op.create_index("ix_glossary_entries_glossary_set_id", "glossary_entries", ["glossary_set_id"], unique=False)

    op.create_table(
        "translation_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", task_status_enum, nullable=False, server_default="pending"),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("stored_filename", sa.String(length=512), nullable=False),
        sa.Column("output_mono_filename", sa.String(length=512), nullable=True),
        sa.Column("output_dual_filename", sa.String(length=512), nullable=True),
        sa.Column("lang_in", sa.String(length=16), nullable=False),
        sa.Column("lang_out", sa.String(length=16), nullable=False),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("custom_models.id"), nullable=True),
        sa.Column("glossary_id", sa.Integer(), sa.ForeignKey("glossary_sets.id"), nullable=True),
        sa.Column("pages", sa.String(length=256), nullable=True),
        sa.Column("extra_body", sa.JSON(), nullable=True),
        sa.Column("no_dual", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("no_mono", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("use_alternating_pages_dual", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enhance_compatibility", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ocr_workaround", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("skip_translation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("custom_system_prompt", sa.Text(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queue_position", sa.Integer(), nullable=True),
    )
    op.create_index("ix_translation_tasks_user_id", "translation_tasks", ["user_id"], unique=False)
    op.create_index("ix_translation_tasks_status", "translation_tasks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_translation_tasks_status", table_name="translation_tasks")
    op.drop_index("ix_translation_tasks_user_id", table_name="translation_tasks")
    op.drop_table("translation_tasks")

    op.drop_index("ix_glossary_entries_glossary_set_id", table_name="glossary_entries")
    op.drop_table("glossary_entries")

    op.drop_index("ix_custom_models_user_id", table_name="custom_models")
    op.drop_table("custom_models")

    op.drop_index("ix_glossary_sets_user_id", table_name="glossary_sets")
    op.drop_table("glossary_sets")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

    task_status_enum = postgresql.ENUM(
        "pending",
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="taskstatus",
        create_type=False,
    )
    user_role_enum = postgresql.ENUM("user", "admin", name="userrole", create_type=False)
    task_status_enum.drop(op.get_bind(), checkfirst=True)
    user_role_enum.drop(op.get_bind(), checkfirst=True)