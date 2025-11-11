"""
Сервис управления отгрузками готовой продукции.

Этот модуль предоставляет функциональность для:
- Управления получателями (контрагентами)
- Создания и управления отгрузками
- Резервирования готовой продукции под отгрузку
- Выполнения отгрузки с FIFO-логикой
- Отмены и корректировки отгрузок
- Статистики и отчетности по отгрузкам
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import Session, selectinload

from app.database.models import (
    Shipment, ShipmentItem, Recipient, Stock, SKU, Movement,
    InventoryReserve, User, Warehouse,
    ShipmentStatus, MovementType, SKUType, ReserveType
)
from app.utils.calculations import (
    get_fifo_stock_for_shipment,
    calculate_stock_availability,
    validate_quantity
)


# ============================================================================
# УПРАВЛЕНИЕ ПОЛУЧАТЕЛЯМИ
# ============================================================================

async def create_recipient(
    session: Session,
    name: str,
    contact_info: Optional[str] = None,
    address: Optional[str] = None,
    tax_id: Optional[str] = None,
    notes: Optional[str] = None
) -> Recipient:
    """
    Создает нового получателя (контрагента).
    
    Args:
        session: Сессия БД
        name: Название организации или ФИО
        contact_info: Контактная информация (телефон, email)
        address: Юридический/фактический адрес
        tax_id: ИНН или другой налоговый идентификатор
        notes: Дополнительные заметки
        
    Returns:
        Recipient: Созданный получатель
        
    Raises:
        ValueError: Если получатель с таким именем уже существует
    """
    # Проверка на дубликат
    stmt = select(Recipient).where(
        Recipient.name == name,
        Recipient.is_active == True
    )
    existing = await session.scalar(stmt)
    
    if existing:
        raise ValueError(f"Получатель '{name}' уже существует")
    
    # Создание нового получателя
    recipient = Recipient(
        name=name,
        contact_info=contact_info,
        address=address,
        tax_id=tax_id,
        notes=notes,
        is_active=True
    )
    
    session.add(recipient)
    await session.commit()
    await session.refresh(recipient)
    
    return recipient


async def get_recipients(
    session: Session,
    active_only: bool = True,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Recipient]:
    """
    Получает список получателей с фильтрацией.
    
    Args:
        session: Сессия БД
        active_only: Только активные получатели
        search: Поисковый запрос по названию
        limit: Максимальное количество записей
        offset: Смещение для пагинации
        
    Returns:
        List[Recipient]: Список получателей
    """
    stmt = select(Recipient)
    
    # Фильтры
    if active_only:
        stmt = stmt.where(Recipient.is_active == True)
    
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Recipient.name.ilike(search_pattern),
                Recipient.contact_info.ilike(search_pattern)
            )
        )
    
    # Сортировка и пагинация
    stmt = stmt.order_by(Recipient.name).limit(limit).offset(offset)
    
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_recipient(
    session: Session,
    recipient_id: int,
    name: Optional[str] = None,
    contact_info: Optional[str] = None,
    address: Optional[str] = None,
    tax_id: Optional[str] = None,
    notes: Optional[str] = None,
    is_active: Optional[bool] = None
) -> Recipient:
    """
    Обновляет данные получателя.
    
    Args:
        session: Сессия БД
        recipient_id: ID получателя
        name: Новое название (опционально)
        contact_info: Новая контактная информация
        address: Новый адрес
        tax_id: Новый ИНН
        notes: Новые заметки
        is_active: Статус активности
        
    Returns:
        Recipient: Обновленный получатель
        
    Raises:
        ValueError: Если получатель не найден
    """
    recipient = await session.get(Recipient, recipient_id)
    if not recipient:
        raise ValueError(f"Получатель с ID {recipient_id} не найден")
    
    # Обновление полей
    if name is not None:
        # Проверка на дубликат при изменении имени
        if name != recipient.name:
            stmt = select(Recipient).where(
                Recipient.name == name,
                Recipient.id != recipient_id,
                Recipient.is_active == True
            )
            existing = await session.scalar(stmt)
            if existing:
                raise ValueError(f"Получатель '{name}' уже существует")
        recipient.name = name
    
    if contact_info is not None:
        recipient.contact_info = contact_info
    if address is not None:
        recipient.address = address
    if tax_id is not None:
        recipient.tax_id = tax_id
    if notes is not None:
        recipient.notes = notes
    if is_active is not None:
        recipient.is_active = is_active
    
    recipient.updated_at = datetime.utcnow()
    
    await session.commit()
    await session.refresh(recipient)
    
    return recipient


async def get_recipient_statistics(
    session: Session,
    recipient_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Dict:
    """
    Получает статистику по получателю.
    
    Args:
        session: Сессия БД
        recipient_id: ID получателя
        start_date: Начало периода
        end_date: Конец периода
        
    Returns:
        Dict: Статистика (количество отгрузок, общий объем, последняя отгрузка)
    """
    recipient = await session.get(Recipient, recipient_id)
    if not recipient:
        raise ValueError(f"Получатель с ID {recipient_id} не найден")
    
    # Базовый запрос
    stmt = select(Shipment).where(Shipment.recipient_id == recipient_id)
    
    # Фильтр по датам
    if start_date:
        stmt = stmt.where(Shipment.shipment_date >= start_date)
    if end_date:
        stmt = stmt.where(Shipment.shipment_date <= end_date)
    
    shipments = (await session.execute(stmt)).scalars().all()
    
    # Подсчет статистики
    total_shipments = len(shipments)
    completed_shipments = len([s for s in shipments if s.status == ShipmentStatus.COMPLETED])
    
    # Последняя отгрузка
    last_shipment = None
    if shipments:
        last_shipment = max(shipments, key=lambda s: s.shipment_date)
    
    # Общий объем по SKU
    sku_volumes = {}
    for shipment in shipments:
        if shipment.status == ShipmentStatus.COMPLETED:
            for item in shipment.items:
                sku_name = item.sku.name
                if sku_name not in sku_volumes:
                    sku_volumes[sku_name] = Decimal('0')
                sku_volumes[sku_name] += item.quantity
    
    return {
        'recipient': recipient,
        'total_shipments': total_shipments,
        'completed_shipments': completed_shipments,
        'cancelled_shipments': total_shipments - completed_shipments,
        'last_shipment_date': last_shipment.shipment_date if last_shipment else None,
        'sku_volumes': sku_volumes,
        'period': {
            'start': start_date,
            'end': end_date
        }
    }


# ============================================================================
# СОЗДАНИЕ И УПРАВЛЕНИЕ ОТГРУЗКАМИ
# ============================================================================

async def create_shipment(
    session: Session,
    warehouse_id: int,
    recipient_id: int,
    created_by_id: int,
    shipment_date: date,
    notes: Optional[str] = None
) -> Shipment:
    """
    Создает новую отгрузку (черновик).
    
    Args:
        session: Сессия БД
        warehouse_id: ID склада
        recipient_id: ID получателя
        created_by_id: ID пользователя-создателя
        shipment_date: Дата отгрузки
        notes: Примечания
        
    Returns:
        Shipment: Созданная отгрузка
        
    Raises:
        ValueError: Если склад/получатель не найдены
    """
    # Проверка существования склада
    warehouse = await session.get(Warehouse, warehouse_id)
    if not warehouse:
        raise ValueError(f"Склад с ID {warehouse_id} не найден")
    
    # Проверка существования получателя
    recipient = await session.get(Recipient, recipient_id)
    if not recipient or not recipient.is_active:
        raise ValueError(f"Активный получатель с ID {recipient_id} не найден")
    
    # Проверка пользователя
    user = await session.get(User, created_by_id)
    if not user:
        raise ValueError(f"Пользователь с ID {created_by_id} не найден")
    
    # Создание отгрузки
    shipment = Shipment(
        warehouse_id=warehouse_id,
        recipient_id=recipient_id,
        created_by_id=created_by_id,
        shipment_date=shipment_date,
        status=ShipmentStatus.DRAFT,
        notes=notes
    )
    
    session.add(shipment)
    await session.commit()
    await session.refresh(shipment)
    
    return shipment


async def add_shipment_item(
    session: Session,
    shipment_id: int,
    sku_id: int,
    quantity: Decimal,
    price_per_unit: Optional[Decimal] = None
) -> ShipmentItem:
    """
    Добавляет позицию в отгрузку.
    
    Args:
        session: Сессия БД
        shipment_id: ID отгрузки
        sku_id: ID готовой продукции
        quantity: Количество
        price_per_unit: Цена за единицу (опционально)
        
    Returns:
        ShipmentItem: Созданная позиция
        
    Raises:
        ValueError: Если отгрузка не в статусе DRAFT или недостаточно остатков
    """
    # Проверка отгрузки
    shipment = await session.get(
        Shipment,
        shipment_id,
        options=[selectinload(Shipment.items)]
    )
    if not shipment:
        raise ValueError(f"Отгрузка с ID {shipment_id} не найдена")
    
    if shipment.status != ShipmentStatus.DRAFT:
        raise ValueError(f"Нельзя добавить позицию в отгрузку со статусом {shipment.status.value}")
    
    # Проверка SKU
    sku = await session.get(SKU, sku_id)
    if not sku:
        raise ValueError(f"SKU с ID {sku_id} не найден")
    
    if sku.type != SKUType.finished:
        raise ValueError(f"SKU '{sku.name}' не является готовой продукцией")
    
    # Валидация количества
    if not validate_quantity(quantity, min_value=Decimal('0.001')):
        raise ValueError(f"Некорректное количество: {quantity}")
    
    # Проверка доступности на складе
    availability = await calculate_stock_availability(
        session,
        warehouse_id=shipment.warehouse_id,
        sku_id=sku_id
    )
    
    if availability['available'] < quantity:
        raise ValueError(
            f"Недостаточно остатков SKU '{sku.name}'. "
            f"Доступно: {availability['available']} {sku.unit}, "
            f"Запрошено: {quantity} {sku.unit}"
        )
    
    # Проверка на дубликат позиции
    existing_item = next(
        (item for item in shipment.items if item.sku_id == sku_id),
        None
    )
    if existing_item:
        raise ValueError(f"SKU '{sku.name}' уже добавлен в отгрузку. Измените количество существующей позиции.")
    
    # Создание позиции
    item = ShipmentItem(
        shipment_id=shipment_id,
        sku_id=sku_id,
        quantity=quantity,
        price_per_unit=price_per_unit
    )
    
    session.add(item)
    await session.commit()
    await session.refresh(item)
    
    return item


async def update_shipment_item(
    session: Session,
    item_id: int,
    quantity: Optional[Decimal] = None,
    price_per_unit: Optional[Decimal] = None
) -> ShipmentItem:
    """
    Обновляет позицию отгрузки.
    
    Args:
        session: Сессия БД
        item_id: ID позиции
        quantity: Новое количество
        price_per_unit: Новая цена
        
    Returns:
        ShipmentItem: Обновленная позиция
        
    Raises:
        ValueError: Если отгрузка не в статусе DRAFT
    """
    item = await session.get(ShipmentItem, item_id, options=[selectinload(ShipmentItem.shipment)])
    if not item:
        raise ValueError(f"Позиция с ID {item_id} не найдена")
    
    if item.shipment.status != ShipmentStatus.DRAFT:
        raise ValueError(f"Нельзя изменить позицию в отгрузке со статусом {item.shipment.status.value}")
    
    # Обновление количества
    if quantity is not None:
        if not validate_quantity(quantity, min_value=Decimal('0.001')):
            raise ValueError(f"Некорректное количество: {quantity}")
        
        # Проверка доступности
        availability = await calculate_stock_availability(
            session,
            warehouse_id=item.shipment.warehouse_id,
            sku_id=item.sku_id
        )
        
        if availability['available'] < quantity:
            raise ValueError(
                f"Недостаточно остатков. "
                f"Доступно: {availability['available']}, "
                f"Запрошено: {quantity}"
            )
        
        item.quantity = quantity
    
    # Обновление цены
    if price_per_unit is not None:
        if price_per_unit < 0:
            raise ValueError("Цена не может быть отрицательной")
        item.price_per_unit = price_per_unit
    
    await session.commit()
    await session.refresh(item)
    
    return item


async def remove_shipment_item(
    session: Session,
    item_id: int
) -> None:
    """
    Удаляет позицию из отгрузки.
    
    Args:
        session: Сессия БД
        item_id: ID позиции
        
    Raises:
        ValueError: Если отгрузка не в статусе DRAFT
    """
    item = await session.get(ShipmentItem, item_id, options=[selectinload(ShipmentItem.shipment)])
    if not item:
        raise ValueError(f"Позиция с ID {item_id} не найдена")
    
    if item.shipment.status != ShipmentStatus.DRAFT:
        raise ValueError(f"Нельзя удалить позицию из отгрузки со статусом {item.shipment.status.value}")
    
    await session.delete(item)
    await session.commit()


# ============================================================================
# РЕЗЕРВИРОВАНИЕ ПРОДУКЦИИ
# ============================================================================

async def reserve_for_shipment(
    session: Session,
    shipment_id: int,
    user_id: int
) -> List[InventoryReserve]:
    """
    Резервирует готовую продукцию под отгрузку.
    
    Переводит отгрузку в статус RESERVED и создает резервы по всем позициям.
    
    Args:
        session: Сессия БД
        shipment_id: ID отгрузки
        user_id: ID пользователя, выполняющего резервирование
        
    Returns:
        List[InventoryReserve]: Список созданных резервов
        
    Raises:
        ValueError: Если отгрузка не в статусе DRAFT или недостаточно остатков
    """
    # Загрузка отгрузки с позициями
    stmt = select(Shipment).where(Shipment.id == shipment_id).options(
        selectinload(Shipment.items).selectinload(ShipmentItem.sku)
    )
    shipment = await session.scalar(stmt)
    
    if not shipment:
        raise ValueError(f"Отгрузка с ID {shipment_id} не найдена")
    
    if shipment.status != ShipmentStatus.DRAFT:
        raise ValueError(f"Резервирование возможно только для отгрузок в статусе DRAFT")
    
    if not shipment.items:
        raise ValueError("Отгрузка не содержит позиций")
    
    # Проверка доступности всех позиций
    for item in shipment.items:
        availability = await calculate_stock_availability(
            session,
            warehouse_id=shipment.warehouse_id,
            sku_id=item.sku_id
        )
        
        if availability['available'] < item.quantity:
            raise ValueError(
                f"Недостаточно остатков для резервирования '{item.sku.name}'. "
                f"Доступно: {availability['available']} {item.sku.unit}, "
                f"Требуется: {item.quantity} {item.sku.unit}"
            )
    
    # Создание резервов
    reserves = []
    for item in shipment.items:
        reserve = InventoryReserve(
            warehouse_id=shipment.warehouse_id,
            sku_id=item.sku_id,
            quantity=item.quantity,
            reserve_type=ReserveType.SHIPMENT,
            reference_id=shipment.id,
            reserved_by_id=user_id,
            reserved_until=shipment.shipment_date + timedelta(days=7),  # Резерв на неделю
            notes=f"Резерв для отгрузки #{shipment.id}"
        )
        session.add(reserve)
        reserves.append(reserve)
    
    # Обновление статуса отгрузки
    shipment.status = ShipmentStatus.RESERVED
    shipment.updated_at = datetime.utcnow()
    
    await session.commit()
    
    # Обновление объектов
    for reserve in reserves:
        await session.refresh(reserve)
    await session.refresh(shipment)
    
    return reserves


async def cancel_shipment_reservation(
    session: Session,
    shipment_id: int
) -> None:
    """
    Отменяет резервирование под отгрузку.
    
    Удаляет все резервы и возвращает отгрузку в статус DRAFT.
    
    Args:
        session: Сессия БД
        shipment_id: ID отгрузки
        
    Raises:
        ValueError: Если отгрузка не в статусе RESERVED
    """
    shipment = await session.get(Shipment, shipment_id)
    if not shipment:
        raise ValueError(f"Отгрузка с ID {shipment_id} не найдена")
    
    if shipment.status != ShipmentStatus.RESERVED:
        raise ValueError(f"Отмена резервирования возможна только для статуса RESERVED")
    
    # Удаление всех резервов
    stmt = select(InventoryReserve).where(
        InventoryReserve.reserve_type == ReserveType.SHIPMENT,
        InventoryReserve.reference_id == shipment_id
    )
    reserves = (await session.execute(stmt)).scalars().all()
    
    for reserve in reserves:
        await session.delete(reserve)
    
    # Возврат в DRAFT
    shipment.status = ShipmentStatus.DRAFT
    shipment.updated_at = datetime.utcnow()
    
    await session.commit()


# ============================================================================
# ВЫПОЛНЕНИЕ ОТГРУЗКИ
# ============================================================================

async def execute_shipment(
    session: Session,
    shipment_id: int,
    user_id: int,
    actual_shipment_date: Optional[date] = None
) -> Tuple[Shipment, List[Movement]]:
    """
    Выполняет отгрузку готовой продукции с FIFO-логикой.
    
    Процесс:
    1. Проверка статуса отгрузки (должен быть RESERVED)
    2. Списание продукции со склада по FIFO
    3. Создание движений на отгрузку
    4. Удаление резервов
    5. Обновление статуса на COMPLETED
    
    Args:
        session: Сессия БД
        shipment_id: ID отгрузки
        user_id: ID пользователя, выполняющего отгрузку
        actual_shipment_date: Фактическая дата отгрузки (если отличается от плановой)
        
    Returns:
        Tuple[Shipment, List[Movement]]: Отгрузка и список созданных движений
        
    Raises:
        ValueError: Если отгрузка не в статусе RESERVED или недостаточно остатков
    """
    # Загрузка отгрузки
    stmt = select(Shipment).where(Shipment.id == shipment_id).options(
        selectinload(Shipment.items).selectinload(ShipmentItem.sku),
        selectinload(Shipment.recipient)
    )
    shipment = await session.scalar(stmt)
    
    if not shipment:
        raise ValueError(f"Отгрузка с ID {shipment_id} не найдена")
    
    if shipment.status != ShipmentStatus.RESERVED:
        raise ValueError(f"Выполнение возможно только для зарезервированных отгрузок")
    
    if not shipment.items:
        raise ValueError("Отгрузка не содержит позиций")
    
    # Дата отгрузки
    shipment_date = actual_shipment_date or shipment.shipment_date
    
    # Выполнение отгрузки по позициям
    movements = []
    
    for item in shipment.items:
        # Получение FIFO-остатков
        fifo_stocks = await get_fifo_stock_for_shipment(
            session,
            warehouse_id=shipment.warehouse_id,
            sku_id=item.sku_id,
            required_quantity=item.quantity
        )
        
        if not fifo_stocks:
            raise ValueError(
                f"Недостаточно остатков для отгрузки '{item.sku.name}'. "
                f"Требуется: {item.quantity} {item.sku.unit}"
            )
        
        # Проверка достаточности остатков
        total_available = sum(stock['available_quantity'] for stock in fifo_stocks)
        if total_available < item.quantity:
            raise ValueError(
                f"Недостаточно остатков '{item.sku.name}'. "
                f"Доступно: {total_available} {item.sku.unit}, "
                f"Требуется: {item.quantity} {item.sku.unit}"
            )
        
        # Списание по FIFO
        remaining_quantity = item.quantity
        
        for stock_info in fifo_stocks:
            if remaining_quantity <= 0:
                break
            
            stock = stock_info['stock']
            to_deduct = min(remaining_quantity, stock_info['available_quantity'])
            
            # Создание движения на списание
            movement = Movement(
                warehouse_id=shipment.warehouse_id,
                sku_id=item.sku_id,
                movement_type=MovementType.SHIPMENT,
                quantity=-to_deduct,  # Отрицательное значение для списания
                reference_type='shipment',
                reference_id=shipment.id,
                performed_by_id=user_id,
                notes=f"Отгрузка #{shipment.id} для '{shipment.recipient.name}'"
            )
            session.add(movement)
            movements.append(movement)
            
            # Обновление остатка
            stock.quantity -= to_deduct
            stock.updated_at = datetime.utcnow()
            
            # Удаление пустых остатков
            if stock.quantity <= 0:
                await session.delete(stock)
            
            remaining_quantity -= to_deduct
    
    # Удаление резервов
    stmt = select(InventoryReserve).where(
        InventoryReserve.reserve_type == ReserveType.SHIPMENT,
        InventoryReserve.reference_id == shipment_id
    )
    reserves = (await session.execute(stmt)).scalars().all()
    for reserve in reserves:
        await session.delete(reserve)
    
    # Обновление статуса отгрузки
    shipment.status = ShipmentStatus.COMPLETED
    shipment.shipment_date = shipment_date
    shipment.updated_at = datetime.utcnow()
    
    await session.commit()
    
    # Обновление объектов
    for movement in movements:
        await session.refresh(movement)
    await session.refresh(shipment)
    
    return shipment, movements


# ============================================================================
# ОТМЕНА И КОРРЕКТИРОВКА ОТГРУЗОК
# ============================================================================

async def cancel_shipment(
    session: Session,
    shipment_id: int,
    user_id: int,
    cancellation_reason: Optional[str] = None
) -> Shipment:
    """
    Отменяет отгрузку.
    
    Для зарезервированных отгрузок - снимает резервы.
    Для выполненных отгрузок - создает возвратные движения.
    
    Args:
        session: Сессия БД
        shipment_id: ID отгрузки
        user_id: ID пользователя
        cancellation_reason: Причина отмены
        
    Returns:
        Shipment: Отмененная отгрузка
        
    Raises:
        ValueError: Если отгрузка уже отменена
    """
    shipment = await session.get(
        Shipment,
        shipment_id,
        options=[selectinload(Shipment.items).selectinload(ShipmentItem.sku)]
    )
    
    if not shipment:
        raise ValueError(f"Отгрузка с ID {shipment_id} не найдена")
    
    if shipment.status == ShipmentStatus.CANCELLED:
        raise ValueError("Отгрузка уже отменена")
    
    # Обработка в зависимости от статуса
    if shipment.status == ShipmentStatus.RESERVED:
        # Снятие резервов
        await cancel_shipment_reservation(session, shipment_id)
    
    elif shipment.status == ShipmentStatus.COMPLETED:
        # Возврат продукции на склад
        for item in shipment.items:
            # Создание обратного движения
            movement = Movement(
                warehouse_id=shipment.warehouse_id,
                sku_id=item.sku_id,
                movement_type=MovementType.ADJUSTMENT,
                quantity=item.quantity,  # Положительное значение для возврата
                reference_type='shipment_cancellation',
                reference_id=shipment.id,
                performed_by_id=user_id,
                notes=f"Отмена отгрузки #{shipment.id}. Причина: {cancellation_reason or 'Не указана'}"
            )
            session.add(movement)
            
            # Восстановление остатка
            stmt = select(Stock).where(
                Stock.warehouse_id == shipment.warehouse_id,
                Stock.sku_id == item.sku_id,
                Stock.batch_number.is_(None)  # Общий остаток без партии
            )
            stock = await session.scalar(stmt)
            
            if stock:
                stock.quantity += item.quantity
                stock.updated_at = datetime.utcnow()
            else:
                # Создание нового остатка
                stock = Stock(
                    warehouse_id=shipment.warehouse_id,
                    sku_id=item.sku_id,
                    quantity=item.quantity,
                    batch_number=None
                )
                session.add(stock)
    
    # Обновление статуса
    shipment.status = ShipmentStatus.CANCELLED
    shipment.notes = f"{shipment.notes or ''}\n[ОТМЕНЕНО] {cancellation_reason or 'Причина не указана'}"
    shipment.updated_at = datetime.utcnow()
    
    await session.commit()
    await session.refresh(shipment)
    
    return shipment


# ============================================================================
# СТАТИСТИКА И ОТЧЕТНОСТЬ
# ============================================================================

async def get_shipments(
    session: Session,
    warehouse_id: Optional[int] = None,
    recipient_id: Optional[int] = None,
    status: Optional[ShipmentStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Shipment]:
    """
    Получает список отгрузок с фильтрацией.
    
    Args:
        session: Сессия БД
        warehouse_id: Фильтр по складу
        recipient_id: Фильтр по получателю
        status: Фильтр по статусу
        start_date: Начало периода
        end_date: Конец периода
        limit: Максимальное количество записей
        offset: Смещение для пагинации
        
    Returns:
        List[Shipment]: Список отгрузок
    """
    stmt = select(Shipment).options(
        selectinload(Shipment.recipient),
        selectinload(Shipment.warehouse),
        selectinload(Shipment.items).selectinload(ShipmentItem.sku)
    )
    
    # Фильтры
    if warehouse_id:
        stmt = stmt.where(Shipment.warehouse_id == warehouse_id)
    if recipient_id:
        stmt = stmt.where(Shipment.recipient_id == recipient_id)
    if status:
        stmt = stmt.where(Shipment.status == status)
    if start_date:
        stmt = stmt.where(Shipment.shipment_date >= start_date)
    if end_date:
        stmt = stmt.where(Shipment.shipment_date <= end_date)
    
    # Сортировка и пагинация
    stmt = stmt.order_by(desc(Shipment.shipment_date)).limit(limit).offset(offset)
    
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_shipment_statistics(
    session: Session,
    warehouse_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Dict:
    """
    Получает статистику по отгрузкам.
    
    Args:
        session: Сессия БД
        warehouse_id: Фильтр по складу
        start_date: Начало периода
        end_date: Конец периода
        
    Returns:
        Dict: Статистика по отгрузкам
    """
    # Базовый запрос
    stmt = select(Shipment).options(
        selectinload(Shipment.items).selectinload(ShipmentItem.sku)
    )
    
    # Фильтры
    if warehouse_id:
        stmt = stmt.where(Shipment.warehouse_id == warehouse_id)
    if start_date:
        stmt = stmt.where(Shipment.shipment_date >= start_date)
    if end_date:
        stmt = stmt.where(Shipment.shipment_date <= end_date)
    
    shipments = (await session.execute(stmt)).scalars().all()
    
    # Подсчет по статусам
    status_counts = {}
    for status in ShipmentStatus:
        status_counts[status.value] = len([s for s in shipments if s.status == status])
    
    # Объем по SKU (только завершенные)
    sku_volumes = {}
    total_value = Decimal('0')
    
    for shipment in shipments:
        if shipment.status == ShipmentStatus.COMPLETED:
            for item in shipment.items:
                sku_name = item.sku.name
                if sku_name not in sku_volumes:
                    sku_volumes[sku_name] = {
                        'quantity': Decimal('0'),
                        'unit': item.sku.unit
                    }
                sku_volumes[sku_name]['quantity'] += item.quantity
                
                if item.price_per_unit:
                    total_value += item.quantity * item.price_per_unit
    
    # Топ-5 получателей
    recipient_volumes = {}
    for shipment in shipments:
        if shipment.status == ShipmentStatus.COMPLETED:
            recipient_name = shipment.recipient.name
            if recipient_name not in recipient_volumes:
                recipient_volumes[recipient_name] = 0
            recipient_volumes[recipient_name] += 1
    
    top_recipients = sorted(
        recipient_volumes.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    return {
        'total_shipments': len(shipments),
        'by_status': status_counts,
        'sku_volumes': sku_volumes,
        'total_value': total_value,
        'top_recipients': top_recipients,
        'period': {
            'start': start_date,
            'end': end_date
        }
    }


async def get_pending_shipments(
    session: Session,
    warehouse_id: Optional[int] = None,
    overdue_only: bool = False
) -> List[Shipment]:
    """
    Получает список ожидающих отгрузок.
    
    Args:
        session: Сессия БД
        warehouse_id: Фильтр по складу
        overdue_only: Только просроченные
        
    Returns:
        List[Shipment]: Список отгрузок в статусах DRAFT/RESERVED
    """
    stmt = select(Shipment).where(
        Shipment.status.in_([ShipmentStatus.DRAFT, ShipmentStatus.RESERVED])
    ).options(
        selectinload(Shipment.recipient),
        selectinload(Shipment.items).selectinload(ShipmentItem.sku)
    )
    
    if warehouse_id:
        stmt = stmt.where(Shipment.warehouse_id == warehouse_id)
    
    if overdue_only:
        stmt = stmt.where(Shipment.shipment_date < date.today())
    
    stmt = stmt.order_by(Shipment.shipment_date)
    
    result = await session.execute(stmt)
    return list(result.scalars().all())
