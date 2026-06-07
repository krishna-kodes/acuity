"""merge_multiple_heads

Revision ID: a1b90a75f04a
Revises: 0c0c173a8317, b2c3d4e5f6a7
Create Date: 2026-06-08 01:26:24.923770

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b90a75f04a'
down_revision: Union[str, None] = ('0c0c173a8317', 'b2c3d4e5f6a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
