"""merge heads

Revision ID: 86e1d835df5f
Revises: b20c7e5fc413, ebb09656f273
Create Date: 2026-10-02 00:01:44.404494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86e1d835df5f'
down_revision: Union[str, Sequence[str], None] = ('b20c7e5fc413', 'ebb09656f273')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
