"""
Сервис для работы с остатками на складе.

ИСПРАВЛЕНО: Добавлены недостающие функции для handlers
"""
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime

from app.database.models import Stock, SKU, Warehouse, SKUType
from app.logger import get_logger

logger = get_logger("stock_service")


def get_stock(db: Session, warehouse_id: int, sku_id: int) -> Optional[Stock]:
    """Получить остаток товара на складе."""
    return db.execute(
        select(Stock).where(
            Stock.warehouse_id == warehouse_id,
            Stock.sku_id == sku_id
        )
    ).scalar_one_or_none()


def get_warehouse_stock(db: Session, warehouse_id: int) -> List[Stock]:
    """Получить все остатки на складе."""
    return db.execute(
        select(Stock).where(Stock.warehouse_id == warehouse_id)
    ).scalars().all()


def get_sku_stock_all_warehouses(db: Session, sku_id: int) -> List[Stock]:
    """Получить остатки товара на всех складах."""
    return db.execute(
        select(Stock).where(Stock.sku_id == sku_id)
    ).scalars().all()


def update_stock(
    db: Session,
    warehouse_id: int,
    sku_id: int,
    quantity_change: float
) -> Stock:
    """
    Обновить остаток товара на складе.
    quantity_change может быть положительным (приход) или отрицательным (расход).
    """
    stock = get_stock(db, warehouse_id, sku_id)
    
    if not stock:
        # Создаем новую запись остатка
        if quantity_change < 0:
            raise ValueError(f"Невозможно создать остаток с отрицательным количеством: {quantity_change}")
        stock = Stock(
            warehouse_id=warehouse_id,
            sku_id=sku_id,
            quantity=quantity_change
        )
        db.add(stock)
    else:
        # Обновляем существующий остаток
        new_quantity = stock.quantity + quantity_change
        if new_quantity < 0:
            raise ValueError(f"Недостаточно товара на складе. Доступно: {stock.quantity}, требуется: {abs(quantity_change)}")
        stock.quantity = new_quantity
        stock.updated_at = datetime.utcnow()
    
    db.flush()
    db.refresh(stock)
    logger.info(f"Updated stock: warehouse={warehouse_id}, sku={sku_id}, change={quantity_change}, new_qty={stock.quantity}")
    return stock


def check_low_stock(db: Session, warehouse_id: int = None) -> List[dict]:
    """
    Проверить товары с низким остатком (ниже min_stock).
    Возвращает список словарей с информацией о товарах.
    """
    query = select(Stock, SKU).join(SKU).where(Stock.quantity < SKU.min_stock)
    
    if warehouse_id:
        query = query.where(Stock.warehouse_id == warehouse_id)
    
    results = db.execute(query).all()
    
    low_stock_items = []
    for stock, sku in results:
        low_stock_items.append({
            'warehouse_id': stock.warehouse_id,
            'sku_id': sku.id,
            'sku_code': sku.code,
            'sku_name': sku.name,
            'current_quantity': stock.quantity,
            'min_stock': sku.min_stock,
            'unit': sku.unit
        })
    
    return low_stock_items


def get_total_stock_value(db: Session, warehouse_id: int = None) -> dict:
    """Получить общую статистику по остаткам."""
    query = select(Stock)
    if warehouse_id:
        query = query.where(Stock.warehouse_id == warehouse_id)
    
    stocks = db.execute(query).scalars().all()
    
    total_items = len(stocks)
    total_quantity = sum(s.quantity for s in stocks)
    
    return {
        'total_items': total_items,
        'total_quantity': total_quantity
    }


# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ HANDLERS (NEW!)
# ============================================================================

def calculate_stock_availability(
    db: Session,
    warehouse_id: int,
    sku_id: int
) -> Dict:
    """
    Расчёт доступности остатков с учётом резервов.
    
    Args:
        db: Сессия БД
        warehouse_id: ID склада
        sku_id: ID номенклатуры
        
    Returns:
        Dict: {
            'total_quantity': float,
            'reserved_quantity': float,
            'available_quantity': float
        }
    """
    from app.database.models import InventoryReserve
    
    # Получаем общий остаток
    stock = get_stock(db, warehouse_id, sku_id)
    total_quantity = stock.quantity if stock else 0.0
    
    # Получаем зарезервированное количество
    reserved_query = select(func.sum(InventoryReserve.quantity)).where(
        and_(
            InventoryReserve.warehouse_id == warehouse_id,
            InventoryReserve.sku_id == sku_id,
            InventoryReserve.is_active == True
        )
    )
    reserved_quantity = db.execute(reserved_query).scalar() or 0.0
    
    # Доступное = общее - зарезервированное
    available_quantity = total_quantity - reserved_quantity
    
    logger.debug(
        f"Доступность SKU {sku_id} на складе {warehouse_id}: "
        f"total={total_quantity}, reserved={reserved_quantity}, available={available_quantity}"
    )
    
    return {
        'total_quantity': total_quantity,
        'reserved_quantity': reserved_quantity,
        'available_quantity': max(0, available_quantity)
    }


def create_sku(
    db: Session,
    code: str,
    name: str,
    type: 'SKUType',
    unit: 'Unit' = None,
    category: 'Category' = None,
    min_stock: float = 0.0,
    description: str = None
) -> 'SKU':
    """
    Создание новой номенклатуры.
    
    Args:
        db: Сессия БД
        code: Артикул/код
        name: Название
        type: Тип (raw/semi/finished)
        unit: Единица измерения
        category: Категория
        min_stock: Минимальный остаток
        description: Описание
        
    Returns:
        SKU: Созданная номенклатура
    """
    # Проверка на дубликат кода
    existing = db.execute(
        select(SKU).where(SKU.code == code)
    ).scalar_one_or_none()
    
    if existing:
        raise ValueError(f"Номенклатура с кодом '{code}' уже существует")
    
    sku = SKU(
        code=code,
        name=name,
        type=type,
        unit=unit,
        category=category,
        min_stock=min_stock,
        description=description
    )
    
    db.add(sku)
    db.flush()
    db.refresh(sku)
    
    logger.info(f"Создана номенклатура: {code} - {name} (ID={sku.id})")
    
    return sku


def get_all_skus(db: Session) -> List['SKU']:
    """Получить всю номенклатуру."""
    skus = db.execute(select(SKU)).scalars().all()
    logger.debug(f"Найдено {len(skus)} номенклатур")
    return list(skus)


def get_all_stock_by_warehouse(
    db: Session,
    warehouse_id: int,
    type: 'SKUType' = None
) -> List[Stock]:
    """
    Получить все остатки на складе с возможностью фильтрации по типу.
    
    Args:
        db: Сессия БД
        warehouse_id: ID склада
        type: Фильтр по типу номенклатуры (опционально)
        
    Returns:
        List[Stock]: Список остатков
    """
    query = select(Stock).where(Stock.warehouse_id == warehouse_id)
    
    # Если нужна фильтрация по типу
    if type:
        query = query.join(SKU).where(SKU.type == type)
    
    stocks = db.execute(query).scalars().all()
    logger.debug(f"Найдено {len(stocks)} остатков на складе {warehouse_id}")
    return list(stocks)


def get_sku(db: Session, sku_id: int) -> Optional['SKU']:
    """Получить номенклатуру по ID."""
    return db.execute(
        select(SKU).where(SKU.id == sku_id)
    ).scalar_one_or_none()


async def get_skus_by_type(
    db: AsyncSession,
    type: SKUType,
    active_only: bool = False
) -> List[SKU]:
    """
    Получить номенклатуру по типу.

    Args:
        db: Асинхронная сессия БД
        type: Тип (raw/semi/finished)
        active_only: Только активные номенклатуры

    Returns:
        List[SKU]: Список номенклатур
    """
    query = select(SKU).where(SKU.type == type)

    if active_only:
        query = query.where(SKU.is_active == True)

    result = await db.execute(query)
    skus = result.scalars().all()

    logger.debug(f"Найдено {len(skus)} номенклатур типа {type.value} (active_only={active_only})")
    return list(skus)


async def get_stock_by_warehouse_and_type(
    db: AsyncSession,
    warehouse_id: int,
    type: SKUType
) -> List[Stock]:
    """
    Получить остатки на складе по типу номенклатуры.

    Args:
        db: Асинхронная сессия БД
        warehouse_id: ID склада
        type: Тип номенклатуры (raw/semi/finished)

    Returns:
        List[Stock]: Список остатков
    """
    result = await db.execute(
        select(Stock).join(SKU).where(
            and_(
                Stock.warehouse_id == warehouse_id,
                SKU.type == type
            )
        )
    )
    stocks = result.scalars().all()

    logger.debug(
        f"Найдено {len(stocks)} остатков типа {type.value} на складе {warehouse_id}"
    )
    return list(stocks)


def get_stock_quantity(
    db: Session,
    warehouse_id: int,
    sku_id: int
) -> float:
    """
    Получить количество остатка.
    
    Args:
        db: Сессия БД
        warehouse_id: ID склада
        sku_id: ID номенклатуры
        
    Returns:
        float: Количество (0.0 если остаток не найден)
    """
    stock = get_stock(db, warehouse_id, sku_id)
    return stock.quantity if stock else 0.0


def receive_materials(
    db: Session,
    warehouse_id: int,
    sku_id: int,
    quantity: float,
    user_id: int,
    notes: str = None
) -> Stock:
    """
    Приёмка материалов на склад (приход).

    Args:
        db: Сессия БД
        warehouse_id: ID склада
        sku_id: ID номенклатуры
        quantity: Количество
        user_id: ID пользователя
        notes: Примечания

    Returns:
        Stock: Обновлённый остаток

    Raises:
        ValueError: Если quantity <= 0
    """
    from app.database.models import Movement, MovementType

    if quantity <= 0:
        raise ValueError("Количество должно быть положительным")

    # Обновляем остаток
    stock = update_stock(db, warehouse_id, sku_id, quantity)

    # Создаем movement (приход)
    movement = Movement(
        warehouse_id=warehouse_id,
        sku_id=sku_id,
        type=MovementType.receipt,
        quantity=quantity,
        user_id=user_id,
        notes=notes or "Приёмка материалов"
    )
    db.add(movement)

    db.flush()
    db.refresh(stock)

    logger.info(
        f"Приёмка: склад={warehouse_id}, SKU={sku_id}, "
        f"количество={quantity}, пользователь={user_id}"
    )

    return stock


async def receive_materials_async(
    session: AsyncSession,
    warehouse_id: int,
    sku_id: int,
    quantity: float,
    user_id: int,
    price_per_unit: Optional[float] = None,
    supplier: Optional[str] = None,
    document_number: Optional[str] = None,
    notes: Optional[str] = None
) -> tuple[Stock, 'Movement']:
    """
    Асинхронная приёмка материалов на склад (приход).

    Args:
        session: Async сессия БД
        warehouse_id: ID склада
        sku_id: ID номенклатуры
        quantity: Количество
        user_id: ID пользователя
        price_per_unit: Цена за единицу
        supplier: Поставщик
        document_number: Номер документа
        notes: Примечания

    Returns:
        tuple[Stock, Movement]: Обновлённый остаток и движение

    Raises:
        ValueError: Если quantity <= 0
    """
    from app.database.models import Movement, MovementType
    from decimal import Decimal

    if quantity <= 0:
        raise ValueError("Количество должно быть положительным")

    # Получаем или создаем остаток
    stmt = select(Stock).where(
        Stock.warehouse_id == warehouse_id,
        Stock.sku_id == sku_id
    )
    result = await session.execute(stmt)
    stock = result.scalar_one_or_none()

    if not stock:
        # Создаем новую запись остатка
        stock = Stock(
            warehouse_id=warehouse_id,
            sku_id=sku_id,
            quantity=Decimal(str(quantity))
        )
        session.add(stock)
    else:
        # Обновляем существующий остаток
        stock.quantity += Decimal(str(quantity))
        stock.updated_at = datetime.utcnow()

    # Создаем movement (приход)
    movement = Movement(
        warehouse_id=warehouse_id,
        sku_id=sku_id,
        type=MovementType.receipt,
        quantity=Decimal(str(quantity)),
        price_per_unit=Decimal(str(price_per_unit)) if price_per_unit else None,
        user_id=user_id,
        supplier=supplier,
        document_number=document_number,
        notes=notes or "Приёмка материалов"
    )
    session.add(movement)

    await session.flush()
    await session.refresh(stock)
    await session.refresh(movement)

    logger.info(
        f"Приёмка: склад={warehouse_id}, SKU={sku_id}, "
        f"количество={quantity}, пользователь={user_id}, "
        f"поставщик={supplier}, документ={document_number}"
    )

    return stock, movement
 
