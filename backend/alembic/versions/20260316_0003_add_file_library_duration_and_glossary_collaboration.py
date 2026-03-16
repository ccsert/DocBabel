"""add file library duration and glossary collaboration

Revision ID: 20260316_0003
Revises: 20260316_0002
Create Date: 2026-03-16 01:10:00
"""

from typing import Sequence

import sqlalchemy as sa
import alembic.op as op
from sqlalchemy.dialects import postgresql


revision: str = "20260316_0003"
down_revision: str | None = "20260316_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    op.execute(
        """
        ALTER TABLE translation_tasks
        ADD COLUMN IF NOT EXISTS duration_seconds DOUBLE PRECISION
        """
    )
    op.execute(
        """
        ALTER TABLE glossary_sets
        ADD COLUMN IF NOT EXISTS is_collaborative BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    existing_tables = set(inspector.get_table_names())
    if "glossary_contributions" not in existing_tables:
        status_enum = postgresql.ENUM(
            "pending",
            "approved",
            "rejected",
            name="glossarycontributionstatus",
        )
        status_enum.create(bind, checkfirst=True)
        op.create_table(
            "glossary_contributions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("glossary_set_id", sa.Integer(), sa.ForeignKey("glossary_sets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("proposer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source", sa.String(length=512), nullable=False),
            sa.Column("target", sa.String(length=512), nullable=False),
            sa.Column("target_language", sa.String(length=16), nullable=True),
            sa.Column("status", status_enum, nullable=False, server_default="pending"),
            sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("review_note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("glossary_contributions")} if "glossary_contributions" in set(sa.inspect(bind).get_table_names()) else set()
    if "ix_glossary_contributions_glossary_set_id" not in existing_indexes:
        op.create_index("ix_glossary_contributions_glossary_set_id", "glossary_contributions", ["glossary_set_id"], unique=False)
    if "ix_glossary_contributions_proposer_user_id" not in existing_indexes:
        op.create_index("ix_glossary_contributions_proposer_user_id", "glossary_contributions", ["proposer_user_id"], unique=False)
    if "ix_glossary_contributions_status" not in existing_indexes:
        op.create_index("ix_glossary_contributions_status", "glossary_contributions", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "glossary_contributions" in inspector.get_table_names():
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("glossary_contributions")}
        if "ix_glossary_contributions_status" in existing_indexes:
            op.drop_index("ix_glossary_contributions_status", table_name="glossary_contributions")
        if "ix_glossary_contributions_proposer_user_id" in existing_indexes:
            op.drop_index("ix_glossary_contributions_proposer_user_id", table_name="glossary_contributions")
        if "ix_glossary_contributions_glossary_set_id" in existing_indexes:
            op.drop_index("ix_glossary_contributions_glossary_set_id", table_name="glossary_contributions")
        op.drop_table("glossary_contributions")
    op.execute(
        """
        ALTER TABLE glossary_sets
        DROP COLUMN IF EXISTS is_collaborative
        """
    )
    op.execute(
        """
        ALTER TABLE translation_tasks
        DROP COLUMN IF EXISTS duration_seconds
        """
    )
