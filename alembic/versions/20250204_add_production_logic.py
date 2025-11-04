"""Add production logic: barrels, recipes, packing, shipment

Revision ID: 20250204_001
Revises: 20250127_initial_migration
Create Date: 2025-02-04 12:00:00.000000

Добавляет полную логику производства:
- Обновление enum типов (SKUType, MovementType)
- Технологические карты (technological_cards, recipe_components)
- Производство (production_batches, barrels)
- Фасовка (packing_variants)
- Отгрузка (recipients, shipments, shipment_items)
- Дополнительно (inventory_reserves, waste_records)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250204_001'
down_revision = '20250127_initial_migration'
branch_labels = None
depends_on = None


def upgrade():
    """
    Применение миграции: добавление новых таблиц и обновление существующих.
    """
    
    # ========================================================================
    # 1. ОБНОВЛЕНИЕ ENUM ТИПОВ
    # ========================================================================
    
    # Обновление SKUType: добавление 'semi' (полуфабрикаты)
    op.execute("ALTER TYPE skutype ADD VALUE IF NOT EXISTS 'semi'")
    
    # Обновление MovementType: добавление новых типов движений
    op.execute("ALTER TYPE movementtype ADD VALUE IF NOT EXISTS 'production'")
    op.execute("ALTER TYPE movementtype ADD VALUE IF NOT EXISTS 'packing'")
    op.execute("ALTER TYPE movementtype ADD VALUE IF NOT EXISTS 'shipment'")
    op.execute("ALTER TYPE movementtype ADD VALUE IF NOT EXISTS 'waste'")
    
    # Создание новых ENUM типов
    recipe_status_enum = postgresql.ENUM('draft', 'active', 'archived', name='recipestatus', create_type=True)
    recipe_status_enum.create(op.get_bind(), checkfirst=True)
    
    production_status_enum = postgresql.ENUM('planned', 'in_progress', 'completed', 'cancelled', name='productionstatus', create_type=True)
    production_status_enum.create(op.get_bind(), checkfirst=True)
    
    waste_type_enum = postgresql.ENUM('semifinished_defect', 'container_defect', 'technological_loss', name='wastetype', create_type=True)
    waste_type_enum.create(op.get_bind(), checkfirst=True)
    
    container_type_enum = postgresql.ENUM('bucket', 'can', 'bag', 'bottle', 'other', name='containertype', create_type=True)
    container_type_enum.create(op.get_bind(), checkfirst=True)
    
    # ========================================================================
    # 2. ТЕХНОЛОГИЧЕСКИЕ КАРТЫ (РЕЦЕПТЫ)
    # ========================================================================
    
    op.create_table(
        'technological_cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('semi_product_id', sa.Integer(), nullable=False),
        sa.Column('yield_percent', sa.Float(), nullable=False),
        sa.Column('status', recipe_status_enum, nullable=False, server_default='draft'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['semi_product_id'], ['skus.id'], name='fk_technological_cards_semi_product'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_technological_cards_created_by'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_technological_cards_id', 'technological_cards', ['id'])
    op.create_index('ix_technological_cards_semi_product_id', 'technological_cards', ['semi_product_id'])
    op.create_index('ix_technological_cards_status', 'technological_cards', ['status'])
    
    op.create_table(
        'recipe_components',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('raw_material_id', sa.Integer(), nullable=False),
        sa.Column('percentage', sa.Float(), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['recipe_id'], ['technological_cards.id'], name='fk_recipe_components_recipe', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['raw_material_id'], ['skus.id'], name='fk_recipe_components_raw_material'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recipe_components_id', 'recipe_components', ['id'])
    op.create_index('ix_recipe_components_recipe_id', 'recipe_components', ['recipe_id'])
    op.create_index('ix_recipe_components_raw_material_id', 'recipe_components', ['raw_material_id'])
    
    # ========================================================================
    # 3. ПРОИЗВОДСТВО (ПАРТИИ И БОЧКИ)
    # ========================================================================
    
    op.create_table(
        'production_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('target_weight', sa.Float(), nullable=False),
        sa.Column('actual_weight', sa.Float(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', production_status_enum, nullable=False, server_default='planned'),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['technological_cards.id'], name='fk_production_batches_recipe'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_production_batches_user'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_production_batches_id', 'production_batches', ['id'])
    op.create_index('ix_production_batches_recipe_id', 'production_batches', ['recipe_id'])
    op.create_index('ix_production_batches_user_id', 'production_batches', ['user_id'])
    op.create_index('ix_production_batches_status', 'production_batches', ['status'])
    
    op.create_table(
        'barrels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('semi_product_id', sa.Integer(), nullable=False),
        sa.Column('production_batch_id', sa.Integer(), nullable=False),
        sa.Column('initial_weight', sa.Float(), nullable=False),
        sa.Column('current_weight', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name='fk_barrels_warehouse'),
        sa.ForeignKeyConstraint(['semi_product_id'], ['skus.id'], name='fk_barrels_semi_product'),
        sa.ForeignKeyConstraint(['production_batch_id'], ['production_batches.id'], name='fk_barrels_production_batch'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_barrels_id', 'barrels', ['id'])
    op.create_index('ix_barrels_warehouse_id', 'barrels', ['warehouse_id'])
    op.create_index('ix_barrels_semi_product_id', 'barrels', ['semi_product_id'])
    op.create_index('ix_barrels_production_batch_id', 'barrels', ['production_batch_id'])
    op.create_index('ix_barrels_created_at', 'barrels', ['created_at'])  # Для FIFO
    op.create_index('ix_barrels_is_active', 'barrels', ['is_active'])
    
    # ========================================================================
    # 4. ФАСОВКА
    # ========================================================================
    
    op.create_table(
        'packing_variants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('semi_product_id', sa.Integer(), nullable=False),
        sa.Column('finished_product_id', sa.Integer(), nullable=False),
        sa.Column('container_type', container_type_enum, nullable=False),
        sa.Column('weight_per_unit', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['semi_product_id'], ['skus.id'], name='fk_packing_variants_semi_product'),
        sa.ForeignKeyConstraint(['finished_product_id'], ['skus.id'], name='fk_packing_variants_finished_product'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_packing_variants_id', 'packing_variants', ['id'])
    op.create_index('ix_packing_variants_semi_product_id', 'packing_variants', ['semi_product_id'])
    op.create_index('ix_packing_variants_finished_product_id', 'packing_variants', ['finished_product_id'])
    
    # ========================================================================
    # 5. ОТГРУЗКА
    # ========================================================================
    
    op.create_table(
        'recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('contact_info', sa.String(length=500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recipients_id', 'recipients', ['id'])
    
    op.create_table(
        'shipments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=True),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['recipient_id'], ['recipients.id'], name='fk_shipments_recipient'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name='fk_shipments_warehouse'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_shipments_user'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shipments_id', 'shipments', ['id'])
    op.create_index('ix_shipments_recipient_id', 'shipments', ['recipient_id'])
    op.create_index('ix_shipments_warehouse_id', 'shipments', ['warehouse_id'])
    op.create_index('ix_shipments_user_id', 'shipments', ['user_id'])
    op.create_index('ix_shipments_created_at', 'shipments', ['created_at'])
    
    op.create_table(
        'shipment_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shipment_id', sa.Integer(), nullable=False),
        sa.Column('sku_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], name='fk_shipment_items_shipment', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id'], name='fk_shipment_items_sku'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shipment_items_id', 'shipment_items', ['id'])
    op.create_index('ix_shipment_items_shipment_id', 'shipment_items', ['shipment_id'])
    op.create_index('ix_shipment_items_sku_id', 'shipment_items', ['sku_id'])
    
    # ========================================================================
    # 6. ДОПОЛНИТЕЛЬНЫЕ ТАБЛИЦЫ
    # ========================================================================
    
    op.create_table(
        'inventory_reserves',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('sku_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('reserved_by', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name='fk_inventory_reserves_warehouse'),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id'], name='fk_inventory_reserves_sku'),
        sa.ForeignKeyConstraint(['reserved_by'], ['users.id'], name='fk_inventory_reserves_reserved_by'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_inventory_reserves_id', 'inventory_reserves', ['id'])
    op.create_index('ix_inventory_reserves_warehouse_id', 'inventory_reserves', ['warehouse_id'])
    op.create_index('ix_inventory_reserves_sku_id', 'inventory_reserves', ['sku_id'])
    op.create_index('ix_inventory_reserves_reserved_by', 'inventory_reserves', ['reserved_by'])
    op.create_index('ix_inventory_reserves_expires_at', 'inventory_reserves', ['expires_at'])
    
    op.create_table(
        'waste_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('sku_id', sa.Integer(), nullable=False),
        sa.Column('waste_type', waste_type_enum, nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name='fk_waste_records_warehouse'),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id'], name='fk_waste_records_sku'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_waste_records_user'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_waste_records_id', 'waste_records', ['id'])
    op.create_index('ix_waste_records_warehouse_id', 'waste_records', ['warehouse_id'])
    op.create_index('ix_waste_records_sku_id', 'waste_records', ['sku_id'])
    op.create_index('ix_waste_records_waste_type', 'waste_records', ['waste_type'])
    op.create_index('ix_waste_records_user_id', 'waste_records', ['user_id'])
    op.create_index('ix_waste_records_created_at', 'waste_records', ['created_at'])
    
    # ========================================================================
    # 7. ОБНОВЛЕНИЕ СУЩЕСТВУЮЩЕЙ ТАБЛИЦЫ MOVEMENTS
    # ========================================================================
    
    # Добавление новых полей в таблицу movements
    op.add_column('movements', sa.Column('barrel_id', sa.Integer(), nullable=True))
    op.add_column('movements', sa.Column('production_batch_id', sa.Integer(), nullable=True))
    op.add_column('movements', sa.Column('shipment_id', sa.Integer(), nullable=True))
    
    # Создание foreign keys для новых полей
    op.create_foreign_key('fk_movements_barrel', 'movements', 'barrels', ['barrel_id'], ['id'])
    op.create_foreign_key('fk_movements_production_batch', 'movements', 'production_batches', ['production_batch_id'], ['id'])
    op.create_foreign_key('fk_movements_shipment', 'movements', 'shipments', ['shipment_id'], ['id'])
    
    # Создание индексов для новых полей
    op.create_index('ix_movements_barrel_id', 'movements', ['barrel_id'])
    op.create_index('ix_movements_production_batch_id', 'movements', ['production_batch_id'])
    op.create_index('ix_movements_shipment_id', 'movements', ['shipment_id'])
    
    # ========================================================================
    # 8. УДАЛЕНИЕ СТАРЫХ ТАБЛИЦ (ЕСЛИ ЕСТЬ)
    # ========================================================================
    
    # Удаляем старые таблицы order_items и orders, если они существуют
    # (они заменены на новую логику производства)
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'order_items') THEN
                DROP TABLE IF EXISTS order_items CASCADE;
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'orders') THEN
                DROP TABLE IF EXISTS orders CASCADE;
            END IF;
        END $$;
    """)


def downgrade():
    """
    Откат миграции: удаление добавленных таблиц и полей.
    """
    
    # Удаление индексов и foreign keys из movements
    op.drop_index('ix_movements_shipment_id', 'movements')
    op.drop_index('ix_movements_production_batch_id', 'movements')
    op.drop_index('ix_movements_barrel_id', 'movements')
    
    op.drop_constraint('fk_movements_shipment', 'movements', type_='foreignkey')
    op.drop_constraint('fk_movements_production_batch', 'movements', type_='foreignkey')
    op.drop_constraint('fk_movements_barrel', 'movements', type_='foreignkey')
    
    op.drop_column('movements', 'shipment_id')
    op.drop_column('movements', 'production_batch_id')
    op.drop_column('movements', 'barrel_id')
    
    # Удаление таблиц в обратном порядке (из-за foreign keys)
    op.drop_table('waste_records')
    op.drop_table('inventory_reserves')
    op.drop_table('shipment_items')
    op.drop_table('shipments')
    op.drop_table('recipients')
    op.drop_table('packing_variants')
    op.drop_table('barrels')
    op.drop_table('production_batches')
    op.drop_table('recipe_components')
    op.drop_table('technological_cards')
    
    # Удаление ENUM типов
    op.execute("DROP TYPE IF EXISTS containertype")
    op.execute("DROP TYPE IF EXISTS wastetype")
    op.execute("DROP TYPE IF EXISTS productionstatus")
    op.execute("DROP TYPE IF EXISTS recipestatus")
    
    # ВНИМАНИЕ: откат изменений в существующих ENUM типах (skutype, movementtype)
    # требует более сложной логики, так как PostgreSQL не поддерживает
    # удаление значений из ENUM. В production это потребует:
    # 1. Создания нового ENUM без новых значений
    # 2. Миграции данных
    # 3. Замены старого ENUM на новый
    # Для простоты в downgrade мы их не трогаем
    
    print("WARNING: ENUM types skutype and movementtype were not reverted.")
    print("Manual intervention may be required if strict rollback is needed.")
