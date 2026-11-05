"""add_ultimo_paso_proyecto

Revision ID: f1a2b3c4d5e6
Revises: 71ad544f109a
Create Date: 2026-11-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "71ad544f109a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proyecto", sa.Column("ultimo_paso", sa.Integer(), nullable=True, server_default="0"))


def downgrade() -> None:
    op.drop_column("proyecto", "ultimo_paso")
