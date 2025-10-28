"""
Сервис для работы с товарами (SKU).
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import SKU, SKUType
from app.logger import get_logger

logger = get_logger("sku_service")


def create_sku(
    db: Session,
    code: str,
    name: str,
    sku_type: SKUType,
    unit: str = "шт",
    min_stock: float = 0
) -> SKU:
    """Создать новый SKU."""
    # Проверка на дубликат кода
    existing = db.execute(
        select(SKU).where(SKU.code == code)
    ).scalar_one_or_none()
    
    if existing:
        raise ValueError(f"SKU с кодом {code} уже существует")
    
    sku = SKU(
        code=code,
        name=name,
        type=sku_type,
        unit=unit,
        min_stock=min_stock
    )
    db.add(sku)
    db.commit()
    db.refresh(sku)
    logger.info(f"Created SKU: {code} - {name} (ID: {sku.id})")
    return sku


def get_sku(db: Session, sku_id: int) -> Optional[SKU]:
    """Получить SKU по ID."""
    return db.execute(
        select(SKU).where(SKU.id == sku_id)
    ).scalar_one_or_none()


def get_sku_by_code(db: Session, code: str) -> Optional[SKU]:
    """Получить SKU по коду."""
    return db.execute(
        select(SKU).where(SKU.code == code)
    ).scalar_one_or_none()


def get_all_skus(db: Session, sku_type: SKUType = None) -> List[SKU]:
    """Получить все SKU, опционально фильтруя по типу."""
    query = select(SKU)
    if sku_type:
        query = query.where(SKU.type == sku_type)
    return db.execute(query).scalars().all()


def update_sku(
    db: Session,
    sku_id: int,
    name: str = None,
    unit: str = None,
    min_stock: float = None
) -> Optional[SKU]:
    """Обновить данные SKU."""
    sku = get_sku(db, sku_id)
    if not sku:
        return None
    
    if name:
        sku.name = name
    if unit:
        sku.unit = unit
    if min_stock is not None:
        sku.min_stock = min_stock
    
    db.commit()
    db.refresh(sku)
    logger.info(f"Updated SKU {sku_id}")
    return sku
