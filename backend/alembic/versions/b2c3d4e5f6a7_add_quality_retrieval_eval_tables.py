"""add quality_logs, retrieval_logs, eval_results tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "176f5886852c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quality_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("phase", sa.String(100), nullable=False),
        sa.Column("score_type", sa.String(100), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_quality_logs_project_id", "quality_logs", ["project_id"])

    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("phase", sa.String(100), nullable=False),
        sa.Column("query_index", sa.Integer, nullable=False),
        sa.Column("n_retrieved", sa.Integer, nullable=False),
        sa.Column("n_reranked", sa.Integer, nullable=False),
        sa.Column("top_score", sa.Float, nullable=False),
        sa.Column("avg_score", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_retrieval_logs_project_id", "retrieval_logs", ["project_id"])

    op.create_table(
        "eval_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("grader", sa.String(100), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_eval_results_run_id", "eval_results", ["run_id"])
    op.create_index("ix_eval_results_grader", "eval_results", ["grader"])


def downgrade() -> None:
    op.drop_index("ix_eval_results_grader", "eval_results")
    op.drop_index("ix_eval_results_run_id", "eval_results")
    op.drop_table("eval_results")

    op.drop_index("ix_retrieval_logs_project_id", "retrieval_logs")
    op.drop_table("retrieval_logs")

    op.drop_index("ix_quality_logs_project_id", "quality_logs")
    op.drop_table("quality_logs")
