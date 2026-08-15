"""add scan photos/description/suggestions support

Revision ID: 2f59073eb4ba
Revises: 6d9a43456f33
Create Date: 2026-08-15 00:18:54.710959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f59073eb4ba'
down_revision: Union[str, Sequence[str], None] = '6d9a43456f33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('scans', sa.Column('description', sa.String(), nullable=True))
    op.add_column('scans', sa.Column('photo_paths', sa.JSON(), nullable=True))
    op.add_column('scans', sa.Column('suggestions', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('scans', 'suggestions')
    op.drop_column('scans', 'photo_paths')
    op.drop_column('scans', 'description')
