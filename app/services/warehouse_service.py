"""
Сервис для работы со складами.

ИСПРАВЛЕНО: Добавлена функция get_warehouses() с параметром active_only
ИСПРАВЛЕНО: Переписано на async/await для AsyncSession
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import Warehouse
from app.logger import get_logger

logger = get_logger("warehouse_service")


async def create_warehouse(
    db: AsyncSession,
    name: str,
    location: str = None,
    is_default: bool = False
) -> Warehouse:
    """Создать новый склад."""
    warehouse = Warehouse(
        name=name,
        location=location,
        is_default=is_default
    )
    db.add(warehouse)
    await db.flush()
    await db.refresh(warehouse)
    logger.info(f"Created warehouse: {name} (ID: {warehouse.id})")
    return warehouse


async def get_warehouse(db: AsyncSession, warehouse_id: int) -> Optional[Warehouse]:
    """Получить склад по ID."""
    result = await db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    )
    return result.scalar_one_or_none()


async def get_default_warehouse(db: AsyncSession) -> Optional[Warehouse]:
    """Получить склад по умолчанию."""
    result = await db.execute(
        select(Warehouse).where(Warehouse.is_default == True)
    )
    warehouse = result.scalar_one_or_none()

    # Если нет склада по умолчанию, берем первый
    if not warehouse:
        result = await db.execute(
            select(Warehouse).limit(1)
        )
        warehouse = result.scalar_one_or_none()

    return warehouse


async def get_all_warehouses(db: AsyncSession) -> List[Warehouse]:
    """Получить все склады."""
    result = await db.execute(select(Warehouse))
    return result.scalars().all()


async def get_warehouses(
    db: AsyncSession,
    active_only: bool = True
) -> List[Warehouse]:
    """
    Получить список складов с фильтрацией.

    Args:
        db: Сессия БД
        active_only: Только активные склады (в данной модели все склады активны)

    Returns:
        List[Warehouse]: Список складов

    Note:
        В текущей модели все склады считаются активными.
        Параметр active_only добавлен для совместимости с handlers.
    """
    # В текущей модели Warehouse нет поля is_active
    # Поэтому возвращаем все склады
    return await get_all_warehouses(db)


async def update_warehouse(
    db: AsyncSession,
    warehouse_id: int,
    name: str = None,
    location: str = None,
    is_default: bool = None
) -> Optional[Warehouse]:
    """Обновить данные склада."""
    warehouse = await get_warehouse(db, warehouse_id)
    if not warehouse:
        return None

    if name:
        warehouse.name = name
    if location:
        warehouse.location = location
    if is_default is not None:
        # Если устанавливаем этот склад как default, снимаем флаг с других
        if is_default:
            result = await db.execute(select(Warehouse))
            for wh in result.scalars().all():
                wh.is_default = False
        warehouse.is_default = is_default

    await db.flush()
    await db.refresh(warehouse)
    logger.info(f"Updated warehouse {warehouse_id}")
    return warehouse


async def set_default_warehouse(db: AsyncSession, warehouse_id: int) -> Optional[Warehouse]:
    """Установить склад как склад по умолчанию."""
    # Снимаем флаг default со всех складов
    result = await db.execute(select(Warehouse))
    for wh in result.scalars().all():
        wh.is_default = False

    # Устанавливаем флаг для выбранного склада
    warehouse = await get_warehouse(db, warehouse_id)
    if warehouse:
        warehouse.is_default = True
        await db.flush()
        await db.refresh(warehouse)
        logger.info(f"Set warehouse {warehouse_id} as default")

    return warehouse
