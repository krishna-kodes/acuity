"""add_structured_proposal

Revision ID: 466ced9bd536
Revises: c7d8e9f0a1b2
Create Date: 2026-06-09 00:30:32.007571

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '466ced9bd536'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('proposals', sa.Column('sections_json', sa.Text(), nullable=True))
    op.add_column('proposals', sa.Column('template_version', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('proposals', 'template_version')
    op.drop_column('proposals', 'sections_json')
