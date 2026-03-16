"""add dedup hash columns for translation tasks

Revision ID: 20260316_0002
Revises: 20260316_0001
Create Date: 2026-03-16 00:20:00
"""

from typing import Sequence

import sqlalchemy as sa
import alembic.op as op


revision: str = "20260316_0002"
down_revision: str | None = "20260316_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE translation_tasks
        ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64)
        """
    )
    op.execute(
        """
        ALTER TABLE translation_tasks
        ADD COLUMN IF NOT EXISTS model_config_hash VARCHAR(64)
        """
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("translation_tasks")}

    if "ix_translation_tasks_file_hash" not in existing_indexes:
        op.create_index("ix_translation_tasks_file_hash", "translation_tasks", ["file_hash"], unique=False)
    if "ix_translation_tasks_model_config_hash" not in existing_indexes:
        op.create_index(
            "ix_translation_tasks_model_config_hash",
            "translation_tasks",
            ["model_config_hash"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_translation_tasks_model_config_hash", table_name="translation_tasks")
    op.drop_index("ix_translation_tasks_file_hash", table_name="translation_tasks")
    op.execute(
        """
        ALTER TABLE translation_tasks
        DROP COLUMN IF EXISTS model_config_hash
        """
    )
    op.execute(
        """
        ALTER TABLE translation_tasks
        DROP COLUMN IF EXISTS file_hash
        """
    )
