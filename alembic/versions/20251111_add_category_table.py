"""Add Category table and update SKU model

Revision ID: 20251111_001
Revises: 20251110_001
Create Date: 2025-11-11 00:00:00.000000

Изменения:
1. Создание таблицы categories (управляемый справочник категорий)
2. Добавление полей в SKU:
   - category_id (ForeignKey на categories)
   - is_active (Boolean) - активность материала
   - description (Text) - описание
   - notes (Text) - примечания
   - updated_at (DateTime) - дата обновления
3. Миграция данных из ENUM category в таблицу categories
4. Заполнение category_id на основе старого поля category

ВАЖНО: Старое поле category (ENUM) сохраняется для обратной совместимости.
       Его можно будет удалить в следующей миграции после полного перехода.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision = '20251111_001'
down_revision = '20251110_001'
branch_labels = None
depends_on = None


# Маппинг старых категорий (ENUM) на новые
CATEGORY_MAPPING = {
    'Загустители': 'thickeners',
    'Красители': 'colorants',
    'Отдушки': 'fragrances',
    'Основы': 'bases',
    'Добавки': 'additives',
    'Упаковка': 'packaging'
}


def upgrade():
    """
    Применение миграции.
    """
    # ========================================================================
    # 1. Создание таблицы categories
    # ========================================================================
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Индексы для таблицы categories
    op.create_index('ix_categories_id', 'categories', ['id'])
    op.create_index('ix_categories_name', 'categories', ['name'], unique=True)
    op.create_index('ix_categories_code', 'categories', ['code'], unique=True)

    # ========================================================================
    # 2. Заполнение начальных категорий
    # ========================================================================
    categories_table = sa.table(
        'categories',
        sa.column('name', sa.String),
        sa.column('code', sa.String),
        sa.column('description', sa.Text),
        sa.column('sort_order', sa.Integer),
        sa.column('created_at', sa.DateTime)
    )

    now = datetime.now(timezone.utc)

    op.bulk_insert(categories_table, [
        {
            'name': 'Загустители',
            'code': 'thickeners',
            'description': 'Вещества для изменения вязкости продукта',
            'sort_order': 0,
            'created_at': now
        },
        {
            'name': 'Красители',
            'code': 'colorants',
            'description': 'Пигменты и красители для придания цвета',
            'sort_order': 10,
            'created_at': now
        },
        {
            'name': 'Отдушки',
            'code': 'fragrances',
            'description': 'Ароматические композиции и отдушки',
            'sort_order': 20,
            'created_at': now
        },
        {
            'name': 'Основы',
            'code': 'bases',
            'description': 'Базовые компоненты для производства',
            'sort_order': 30,
            'created_at': now
        },
        {
            'name': 'Добавки',
            'code': 'additives',
            'description': 'Функциональные добавки и модификаторы',
            'sort_order': 40,
            'created_at': now
        },
        {
            'name': 'Упаковка',
            'code': 'packaging',
            'description': 'Материалы для упаковки готовой продукции',
            'sort_order': 50,
            'created_at': now
        }
    ])

    # ========================================================================
    # 3. Добавление новых полей в таблицу skus
    # ========================================================================

    # Добавляем category_id
    op.add_column('skus',
        sa.Column('category_id', sa.Integer(), nullable=True)
    )
    op.create_index('ix_skus_category_id', 'skus', ['category_id'])
    op.create_foreign_key(
        'fk_skus_category_id',
        'skus', 'categories',
        ['category_id'], ['id']
    )

    # Добавляем is_active
    op.add_column('skus',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true')
    )
    op.create_index('ix_skus_is_active', 'skus', ['is_active'])

    # Добавляем description
    op.add_column('skus',
        sa.Column('description', sa.Text(), nullable=True)
    )

    # Добавляем notes
    op.add_column('skus',
        sa.Column('notes', sa.Text(), nullable=True)
    )

    # Добавляем updated_at
    op.add_column('skus',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
    )

    # ========================================================================
    # 4. Миграция данных: заполнение category_id на основе старого category
    # ========================================================================

    # Получаем connection для выполнения SQL
    connection = op.get_bind()

    # Для каждого SKU с заполненным старым полем category,
    # находим соответствующую запись в categories и обновляем category_id
    for category_name, category_code in CATEGORY_MAPPING.items():
        # Находим ID категории по названию
        result = connection.execute(
            sa.text("SELECT id FROM categories WHERE name = :name"),
            {"name": category_name}
        )
        category_row = result.fetchone()

        if category_row:
            category_id = category_row[0]

            # Обновляем SKU с этой категорией
            connection.execute(
                sa.text("""
                    UPDATE skus
                    SET category_id = :cat_id
                    WHERE category = :cat_name
                """),
                {"cat_id": category_id, "cat_name": category_name}
            )


def downgrade():
    """
    Откат миграции.
    """
    # Удаляем добавленные поля из skus
    op.drop_index('ix_skus_is_active', 'skus')
    op.drop_index('ix_skus_category_id', 'skus')
    op.drop_constraint('fk_skus_category_id', 'skus', type_='foreignkey')

    op.drop_column('skus', 'updated_at')
    op.drop_column('skus', 'notes')
    op.drop_column('skus', 'description')
    op.drop_column('skus', 'is_active')
    op.drop_column('skus', 'category_id')

    # Удаляем таблицу categories
    op.drop_index('ix_categories_code', 'categories')
    op.drop_index('ix_categories_name', 'categories')
    op.drop_index('ix_categories_id', 'categories')
    op.drop_table('categories')
