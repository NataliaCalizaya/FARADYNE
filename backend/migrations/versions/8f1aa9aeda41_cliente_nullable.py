"""cliente nullable

Revision ID: 8f1aa9aeda41
Revises: 28b217cc43d6
Create Date: 2026-09-29 18:51:05.026852

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f1aa9aeda41'
down_revision: Union[str, Sequence[str], None] = '28b217cc43d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """ALTER TABLE proyecto ALTER COLUMN cliente DROP NOT NULL;"""
    pass


def downgrade() -> None:
    """UPDATE proyecto SET cliente = 'Sin cliente' WHERE cliente IS NULL;
       ALTER TABLE proyecto ALTER COLUMN cliente SET NOT NULL;"""
    pass
