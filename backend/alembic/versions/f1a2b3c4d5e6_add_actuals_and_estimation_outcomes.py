"""add actual_points/remote_state/closed_at to epics+tasks; estimation_outcomes table

Revision ID: f1a2b3c4d5e6
Revises: d40caa69f6fa
Create Date: 2026-06-13 00:00:00.000000

Supports bidirectional sync (read GitHub issue/milestone state back) and the
estimation feedback loop (calibrate future estimates against realized actuals).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'd40caa69f6fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('epics', sa.Column('actual_points', sa.Integer(), nullable=True))
    op.add_column('epics', sa.Column('remote_state', sa.String(length=20), nullable=True))
    op.add_column('epics', sa.Column('closed_at', sa.DateTime(), nullable=True))

    op.add_column('tasks', sa.Column('actual_points', sa.Integer(), nullable=True))
    op.add_column('tasks', sa.Column('remote_state', sa.String(length=20), nullable=True))
    op.add_column('tasks', sa.Column('closed_at', sa.DateTime(), nullable=True))

    op.create_table(
        'estimation_outcomes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('epic_id', sa.Integer(), nullable=True),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('estimated_points', sa.Integer(), nullable=True),
        sa.Column('actual_points', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_estimation_outcomes_project_id', 'estimation_outcomes', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_estimation_outcomes_project_id', table_name='estimation_outcomes')
    op.drop_table('estimation_outcomes')

    op.drop_column('tasks', 'closed_at')
    op.drop_column('tasks', 'remote_state')
    op.drop_column('tasks', 'actual_points')

    op.drop_column('epics', 'closed_at')
    op.drop_column('epics', 'remote_state')
    op.drop_column('epics', 'actual_points')
