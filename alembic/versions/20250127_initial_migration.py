"""Initial migration with all tables

Revision ID: 001
Revises: 
Create Date: 2025-01-27 22:32:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создание enum типов
    op.execute("CREATE TYPE skutype AS ENUM ('raw', 'finished')")
    op.execute("CREATE TYPE movementtype AS ENUM ('in', 'out', 'transfer', 'adjustment')")
    op.execute("CREATE TYPE ordertype AS ENUM ('purchase', 'production', 'sale')")
    op.execute("CREATE TYPE orderstatus AS ENUM ('pending', 'in_progress', 'completed', 'cancelled')")
    
    # Создание таблицы users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )
    
    # Создание таблицы warehouses
    op.create_table(
        'warehouses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создание таблицы skus
    op.create_table(
        'skus',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', sa.Enum('raw', 'finished', name='skutype'), nullable=False),
        sa.Column('unit', sa.String(), nullable=True),
        sa.Column('min_stock', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    
    # Создание таблицы stock
    op.create_table(
        'stock',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('sku_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id']),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создание таблицы movements
    op.create_table(
        'movements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('sku_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.Enum('in', 'out', 'transfer', 'adjustment', name='movementtype'), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('from_warehouse_id', sa.Integer(), nullable=True),
        sa.Column('to_warehouse_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['from_warehouse_id'], ['warehouses.id']),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id']),
        sa.ForeignKeyConstraint(['to_warehouse_id'], ['warehouses.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создание таблицы orders
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_number', sa.String(), nullable=False),
        sa.Column('type', sa.Enum('purchase', 'production', 'sale', name='ordertype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'in_progress', 'completed', 'cancelled', name='orderstatus'), nullable=True),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_number')
    )
    
    # Создание таблицы order_items
    op.create_table(
        'order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('sku_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Удаление таблиц в обратном порядке
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('movements')
    op.drop_table('stock')
    op.drop_table('skus')
    op.drop_table('warehouses')
    op.drop_table('users')
    
    # Удаление enum типов
    op.execute('DROP TYPE IF EXISTS orderstatus')
    op.execute('DROP TYPE IF EXISTS ordertype')
    op.execute('DROP TYPE IF EXISTS movementtype')
    op.execute('DROP TYPE IF EXISTS skutype')
