"""add phase result columns to projects

Revision ID: a1b2c3d4e5f6
Revises: eca5b2e5babb
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'eca5b2e5babb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('tech_stack', sa.JSON(), nullable=True))
    op.add_column('projects', sa.Column('team_suggestion', sa.JSON(), nullable=True))
    op.add_column('projects', sa.Column('effort_estimates', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'effort_estimates')
    op.drop_column('projects', 'team_suggestion')
    op.drop_column('projects', 'tech_stack')
