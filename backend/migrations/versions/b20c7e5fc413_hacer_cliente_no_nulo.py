"""hacer_cliente_no_nulo

Revision ID: b20c7e5fc413
Revises: 28b217cc43d6
Create Date: 2026-10-01 17:14:57.407652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b20c7e5fc413'
down_revision: Union[str, Sequence[str], None] = '28b217cc43d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tu SQL manual aquí
    op.execute("ALTER TABLE proyecto ALTER COLUMN cliente SET NOT NULL;")
    #pass

def downgrade() -> None:
    op.execute("ALTER TABLE proyecto ALTER COLUMN cliente DROP NOT NULL;")
    #pass