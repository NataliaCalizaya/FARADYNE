"""crear memoria descriptiva

Revision ID: d3f1a8c9b2e4
Revises: c4f1a9d2e7b3
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "d3f1a8c9b2e4"
down_revision: Union[str, Sequence[str], None] = "c4f1a9d2e7b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # La tabla puede existir en bases creadas antes de que este módulo fuera
    # incorporado a Alembic. En ese caso solo se registra esta revisión.
    if inspect(op.get_bind()).has_table("memoria_descriptiva"):
        return
    op.create_table(
        "memoria_descriptiva",
        sa.Column("id_memoria", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ruta_pdf", sa.String(length=500), nullable=True),
        sa.Column("declaracion_decreto_351_79", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fecha_generacion", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("id_proyecto", sa.Integer(), sa.ForeignKey("proyecto.id_proyecto", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("id_proyecto", name="uq_memoria_descriptiva_proyecto"),
    )


def downgrade() -> None:
    op.drop_table("memoria_descriptiva")
