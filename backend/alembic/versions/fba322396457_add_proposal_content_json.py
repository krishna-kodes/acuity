"""add_proposal_content_json

Revision ID: fba322396457
Revises: a1b90a75f04a
Create Date: 2026-06-08 01:26:34.219891

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fba322396457'
down_revision: Union[str, None] = 'a1b90a75f04a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("content_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("proposals", "content_json")
