"""crear_usuario_y_fk_proyecto

Revision ID: c4f1a9d2e7b3
Revises: 86e1d835df5f
Create Date: 2026-10-04 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f1a9d2e7b3'
down_revision: Union[str, Sequence[str], None] = '86e1d835df5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usuario',
        sa.Column('id_usuario', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id_usuario'),
    )
    op.create_index('ix_usuario_email', 'usuario', ['email'], unique=True)

    op.add_column('proyecto', sa.Column('id_usuario', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_proyecto_usuario', 'proyecto', 'usuario',
        ['id_usuario'], ['id_usuario'], ondelete='CASCADE',
    )
    op.create_index('ix_proyecto_id_usuario', 'proyecto', ['id_usuario'])


def downgrade() -> None:
    op.drop_index('ix_proyecto_id_usuario', table_name='proyecto')
    op.drop_constraint('fk_proyecto_usuario', 'proyecto', type_='foreignkey')
    op.drop_column('proyecto', 'id_usuario')
    op.drop_index('ix_usuario_email', table_name='usuario')
    op.drop_table('usuario')