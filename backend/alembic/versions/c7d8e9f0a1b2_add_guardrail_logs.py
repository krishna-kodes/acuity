"""add guardrail_logs table

Revision ID: c7d8e9f0a1b2
Revises: 5e51dc50954c
Create Date: 2026-06-08 10:00:00.000000

"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "c7d8e9f0a1b2"
down_revision = "5e51dc50954c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guardrail_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(100), nullable=False),
        sa.Column("layer", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(100), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_guardrail_logs_project_id", "guardrail_logs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_guardrail_logs_project_id", table_name="guardrail_logs")
    op.drop_table("guardrail_logs")
