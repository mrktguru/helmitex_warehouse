"""add_approval_status_to_users

Revision ID: 5c2cb98cb787
Revises: 20251110_001
Create Date: 2025-11-10 22:30:33.121187+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5c2cb98cb787'
down_revision = '20251110_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создать ENUM тип approval_status
    approval_status_enum = postgresql.ENUM('pending', 'approved', 'rejected', name='approvalstatus')
    approval_status_enum.create(op.get_bind(), checkfirst=True)

    # Добавить колонку approval_status в users
    op.add_column('users', sa.Column('approval_status', sa.Enum('pending', 'approved', 'rejected', name='approvalstatus'), nullable=False, server_default='pending'))

    # Создать индекс на approval_status
    op.create_index('ix_users_approval_status', 'users', ['approval_status'], unique=False)


def downgrade() -> None:
    # Удалить индекс
    op.drop_index('ix_users_approval_status', table_name='users')

    # Удалить колонку
    op.drop_column('users', 'approval_status')

    # Удалить ENUM тип
    approval_status_enum = postgresql.ENUM('pending', 'approved', 'rejected', name='approvalstatus')
    approval_status_enum.drop(op.get_bind(), checkfirst=True)
