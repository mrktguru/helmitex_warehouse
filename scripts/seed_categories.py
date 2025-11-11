#!/usr/bin/env python3
"""
Скрипт для заполнения начальных категорий сырья.

Создает базовые категории из старого ENUM CategoryType:
- Загустители
- Красители
- Отдушки
- Основы
- Добавки
- Упаковка

Использование:
    python scripts/seed_categories.py
"""
import sys
import os

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from app.database.db import SessionLocal
from app.services import category_service
from app.logger import get_logger

logger = get_logger("seed_categories")

# Начальные категории (из старого ENUM)
INITIAL_CATEGORIES = [
    {
        "name": "Загустители",
        "code": "thickeners",
        "description": "Вещества для изменения вязкости продукта",
        "sort_order": 0
    },
    {
        "name": "Красители",
        "code": "colorants",
        "description": "Пигменты и красители для придания цвета",
        "sort_order": 10
    },
    {
        "name": "Отдушки",
        "code": "fragrances",
        "description": "Ароматические композиции и отдушки",
        "sort_order": 20
    },
    {
        "name": "Основы",
        "code": "bases",
        "description": "Базовые компоненты для производства",
        "sort_order": 30
    },
    {
        "name": "Добавки",
        "code": "additives",
        "description": "Функциональные добавки и модификаторы",
        "sort_order": 40
    },
    {
        "name": "Упаковка",
        "code": "packaging",
        "description": "Материалы для упаковки готовой продукции",
        "sort_order": 50
    }
]


def seed_categories(db: Session):
    """Создать начальные категории."""
    logger.info("Starting category seeding...")

    created_count = 0
    skipped_count = 0

    for cat_data in INITIAL_CATEGORIES:
        try:
            # Проверяем, существует ли уже категория
            existing = category_service.get_category_by_name(db, cat_data["name"])

            if existing:
                logger.info(f"Category '{cat_data['name']}' already exists, skipping")
                skipped_count += 1
                continue

            # Создаем категорию
            category = category_service.create_category(
                db=db,
                name=cat_data["name"],
                code=cat_data["code"],
                description=cat_data["description"],
                sort_order=cat_data["sort_order"]
            )

            logger.info(f"Created category: {category.name} (ID: {category.id})")
            created_count += 1

        except Exception as e:
            logger.error(f"Error creating category '{cat_data['name']}': {e}")
            db.rollback()
            raise

    db.commit()

    logger.info(f"Category seeding completed: {created_count} created, {skipped_count} skipped")
    return created_count, skipped_count


def main():
    """Главная функция."""
    logger.info("=" * 60)
    logger.info("Category Seeding Script")
    logger.info("=" * 60)

    db = SessionLocal()

    try:
        created, skipped = seed_categories(db)

        print("\n" + "=" * 60)
        print(f"✅ Seeding completed successfully!")
        print(f"   Created: {created}")
        print(f"   Skipped: {skipped}")
        print("=" * 60)

        # Показываем все категории
        all_categories = category_service.get_all_categories(db)
        print(f"\nTotal categories in database: {len(all_categories)}")
        for cat in all_categories:
            print(f"  - {cat.name} (ID: {cat.id}, code: {cat.code})")

    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        print(f"\n❌ Error: {e}")
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
