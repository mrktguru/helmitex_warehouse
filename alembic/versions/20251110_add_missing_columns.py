"""Add missing columns: users.updated_at, technological_cards.is_active, packing_variants.is_active

Revision ID: 20251110_001
Revises: 20250204_001
Create Date: 2025-11-10 18:00:00.000000

Добавляет недостающие поля:
- users.updated_at (DateTime)
- technological_cards.is_active (Boolean)
- packing_variants.is_active (Boolean)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251110_001'
down_revision = '20250204_001'
branch_labels = None
depends_on = None


def upgrade():
    """
    Применение миграции: добавление недостающих колонок.
    """

    # Добавление updated_at в таблицу users
    op.add_column('users',
        sa.Column('updated_at', sa.DateTime(), nullable=True)
    )

    # Добавление is_active в таблицу technological_cards
    op.add_column('technological_cards',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true')
    )
    op.create_index('ix_technological_cards_is_active', 'technological_cards', ['is_active'])

    # Добавление is_active в таблицу packing_variants
    op.add_column('packing_variants',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true')
    )
    op.create_index('ix_packing_variants_is_active', 'packing_variants', ['is_active'])


def downgrade():
    """
    Откат миграции: удаление добавленных колонок.
    """

    # Удаление индексов
    op.drop_index('ix_packing_variants_is_active', 'packing_variants')
    op.drop_index('ix_technological_cards_is_active', 'technological_cards')

    # Удаление колонок
    op.drop_column('packing_variants', 'is_active')
    op.drop_column('technological_cards', 'is_active')
    op.drop_column('users', 'updated_at')
