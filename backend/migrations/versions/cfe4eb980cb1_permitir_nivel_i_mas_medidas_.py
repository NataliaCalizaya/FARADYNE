"""permitir nivel I mas medidas complementarias

Revision ID: cfe4eb980cb1
Revises: d3f1a8c9b2e4
Create Date: 2026-10-26 20:28:04.546774

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfe4eb980cb1'
down_revision: Union[str, Sequence[str], None] = 'd3f1a8c9b2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        'nivel_de_proteccion_nivel_check',
        'nivel_de_proteccion',
        type_='check',
    )

    op.create_check_constraint(
        'nivel_de_proteccion_nivel_check',
        'nivel_de_proteccion',
        "nivel_proteccion IN ('I+', 'I', 'II', 'III', 'IV')",
    )


def downgrade() -> None:
    # Verificar si hay registros que usan I+
    conexion = op.get_bind()
    resultado = conexion.execute(
        sa.text(
            "SELECT COUNT(*) FROM nivel_de_proteccion "
            "WHERE nivel_proteccion = 'I+'"
        )
    ).scalar()

    if resultado > 0:
        raise RuntimeError(
            "No se puede revertir la migración: "
            "existen registros con nivel de protección I+."
        )

    op.drop_constraint(
        'nivel_de_proteccion_nivel_check',
        'nivel_de_proteccion',
        type_='check',
    )

    op.create_check_constraint(
        'nivel_de_proteccion_nivel_check',
        'nivel_de_proteccion',
        "nivel_proteccion IN ('I', 'II', 'III', 'IV')",
    )