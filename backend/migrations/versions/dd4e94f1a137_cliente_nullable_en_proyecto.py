"""cliente nullable en proyecto

Revision ID: dd4e94f1a137
Revises: 8f1aa9aeda41
Create Date: 2026-09-30 23:08:32.882030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd4e94f1a137'
down_revision: Union[str, Sequence[str], None] = '8f1aa9aeda41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'proyecto',
        'cliente',
        existing_type=sa.String(length=255),
        nullable=True
    )

def downgrade() -> None:
    op.execute("UPDATE proyecto SET cliente = 'Sin cliente' WHERE cliente IS NULL")
    op.alter_column(
        'proyecto',
        'cliente',
        existing_type=sa.String(length=255),
        nullable=False
    )
