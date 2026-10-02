"""validar_constraint_mastil

Revision ID: ebb09656f273
Revises: 8f1aa9aeda41
Create Date: 2026-10-01 22:49:56.130028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ebb09656f273'
down_revision: Union[str, Sequence[str], None] = '8f1aa9aeda41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Ejecuta el comando SQL crudo
    op.execute("ALTER TABLE mastil VALIDATE CONSTRAINT fk_mastil_modelo2d;")


def downgrade() -> None:
    """Downgrade schema."""
    pass
