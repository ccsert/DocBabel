"""add task auto glossary columns

Revision ID: 20260316_0001
Revises:
Create Date: 2026-03-16 00:00:00
"""

from typing import Sequence

import alembic.op as op


revision: str = "20260316_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE translation_tasks
        ADD COLUMN IF NOT EXISTS auto_extract_glossary BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    op.execute(
        """
        ALTER TABLE translation_tasks
        ADD COLUMN IF NOT EXISTS extracted_glossary_data JSON
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE translation_tasks
        DROP COLUMN IF EXISTS extracted_glossary_data
        """
    )
    op.execute(
        """
        ALTER TABLE translation_tasks
        DROP COLUMN IF EXISTS auto_extract_glossary
        """
    )
