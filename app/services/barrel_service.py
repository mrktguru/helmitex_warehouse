"""
Сервис для управления бочками с полуфабрикатами.

Основные функции:
- Создание и получение бочек
- FIFO-выборка бочек для фасовки
- Обновление весов бочек при фасовке
- Деактивация пустых бочек
- Статистика по бочкам
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, desc

from app.database.models import Barrel, SKU, SKUType, Warehouse, ProductionBatch
from app.logger import get_logger

logger = get_logger("barrel_service")


# ============================================================================
# СОЗДАНИЕ И ПОЛУЧЕНИЕ БОЧЕК
# ============================================================================

def create_barrel(
    db: Session,
    warehouse_id: int,
    semi_product_id: int,
    production_batch_id: int,
    initial_weight: float
) -> Barrel:
    """
    Создание новой бочки с полуфабрикатом.
    
    Args:
        db: Сессия БД
        warehouse_id: ID склада
        semi_product_id: ID полуфабриката (SKU type='semi')
        production_batch_id: ID партии производства
        initial_weight: Начальный вес полуфабриката (кг)
        
    Returns:
        Barrel: Созданная бочка
        
    Raises:
        ValueError: Если данные невалидны
        
    Example:
        >>> barrel = create_barrel(
        ...     db, warehouse_id=1, semi_product_id=10,
        ...     production_batch_id=5, initial_weight=150.5
        ... )
        >>> print(f"Бочка ID={barrel.id} создана")
    """
    logger.info(
        f"Создание бочки: склад={warehouse_id}, полуфабрикат={semi_product_id}, "
        f"вес={initial_weight} кг"
    )
    
    # Валидация склада
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        raise ValueError(f"Склад с ID={warehouse_id} не найден")
    
    # Валидация полуфабриката
    semi_product = db.get(SKU, semi_product_id)
    if not semi_product:
        raise ValueError(f"Полуфабрикат с ID={semi_product_id} не найден")
    
    if semi_product.type != SKUType.semi:
        raise ValueError(f"SKU ID={semi_product_id} не является полуфабрикатом")
    
    # Валидация партии производства
    batch = db.get(ProductionBatch, production_batch_id)
    if not batch:
        raise ValueError(f"Партия производства ID={production_batch_id} не найдена")
    
    # Валидация веса
    if initial_weight <= 0:
        raise ValueError("Вес бочки должен быть положительным числом")
    
    if initial_weight > 9999:
        raise ValueError("Вес бочки не должен превышать 9999 кг")
    
    # Создаем бочку
    barrel = Barrel(
        warehouse_id=warehouse_id,
        semi_product_id=semi_product_id,
        production_batch_id=production_batch_id,
        initial_weight=initial_weight,
        current_weight=initial_weight,
        is_active=True
    )
    
    db.add(barrel)
    db.flush()
    db.refresh(barrel)
    
    logger.info(f"Бочка ID={barrel.id} создана, вес={initial_weight} кг")
    
    return barrel


def get_barrel_by_id(
    db: Session,
    barrel_id: int,
    load_relations: bool = True
) -> Optional[Barrel]:
    """
    Получение бочки по ID.
    
    Args:
        db: Сессия БД
        barrel_id: ID бочки
        load_relations: Загружать ли связанные данные
        
    Returns:
        Optional[Barrel]: Бочка или None
    """
    query = select(Barrel).where(Barrel.id == barrel_id)
    
    if load_relations:
        query = query.options(
            joinedload(Barrel.semi_product),
            joinedload(Barrel.warehouse),
            joinedload(Barrel.production_batch)
        )
    
    result = db.execute(query)
    return result.scalar_one_or_none()


def get_barrels(
    db: Session,
    warehouse_id: int = None,
    semi_product_id: int = None,
    is_active: bool = None,
    load_relations: bool = False
) -> List[Barrel]:
    """
    Получение списка бочек с фильтрацией.
    
    Args:
        db: Сессия БД
        warehouse_id: Фильтр по складу (опционально)
        semi_product_id: Фильтр по полуфабрикату (опционально)
        is_active: Фильтр по активности (опционально)
        load_relations: Загружать ли связанные данные
        
    Returns:
        List[Barrel]: Список бочек
    """
    query = select(Barrel)
    
    # Фильтры
    if warehouse_id:
        query = query.where(Barrel.warehouse_id == warehouse_id)
    
    if semi_product_id:
        query = query.where(Barrel.semi_product_id == semi_product_id)
    
    if is_active is not None:
        query = query.where(Barrel.is_active == is_active)
    
    # Eager loading
    if load_relations:
        query = query.options(
            joinedload(Barrel.semi_product),
            joinedload(Barrel.warehouse)
        )
    
    # Сортировка по дате создания (FIFO)
    query = query.order_by(Barrel.created_at)
    
    result = db.execute(query)
    barrels = result.scalars().unique().all()
    
    logger.debug(
        f"Найдено {len(barrels)} бочек "
        f"(warehouse={warehouse_id}, semi_product={semi_product_id}, active={is_active})"
    )
    
    return list(barrels)


def get_active_barrels(
    db: Session,
    warehouse_id: int = None,
    semi_product_id: int = None
) -> List[Barrel]:
    """
    Получение активных бочек (с остатком > 0).
    
    Args:
        db: Сессия БД
        warehouse_id: Фильтр по складу (опционально)
        semi_product_id: Фильтр по полуфабрикату (опционально)
        
    Returns:
        List[Barrel]: Список активных бочек
    """
    query = select(Barrel).where(
        and_(
            Barrel.is_active == True,
            Barrel.current_weight > 0
        )
    )
    
    if warehouse_id:
        query = query.where(Barrel.warehouse_id == warehouse_id)
    
    if semi_product_id:
        query = query.where(Barrel.semi_product_id == semi_product_id)
    
    query = query.options(joinedload(Barrel.semi_product))
    query = query.order_by(Barrel.created_at)  # FIFO
    
    result = db.execute(query)
    barrels = result.scalars().unique().all()
    
    logger.debug(f"Найдено {len(barrels)} активных бочек")
    
    return list(barrels)


# ============================================================================
# FIFO-ВЫБОРКА ДЛЯ ФАСОВКИ
# ============================================================================

def get_barrels_fifo(
    db: Session,
    semi_product_id: int,
    required_weight: float,
    warehouse_id: int = None
) -> Tuple[List[Barrel], float]:
    """
    FIFO-выборка бочек для фасовки.
    
    Возвращает бочки в порядке создания (FIFO),
    достаточные для покрытия требуемого веса.
    
    Args:
        db: Сессия БД
        semi_product_id: ID полуфабриката
        required_weight: Требуемый вес (кг)
        warehouse_id: ID склада (опционально)
        
    Returns:
        Tuple[List[Barrel], float]:
            - Список бочек (отсортирован по FIFO)
            - Общий доступный вес в выбранных бочках
            
    Raises:
        ValueError: Если недостаточно полуфабриката
        
    Example:
        >>> barrels, total_weight = get_barrels_fifo(
        ...     db, semi_product_id=10, required_weight=100.0
        ... )
        >>> print(f"Выбрано {len(barrels)} бочек, вес={total_weight} кг")
    """
    logger.info(f"FIFO-выборка бочек: полуфабрикат={semi_product_id}, требуется={required_weight} кг")
    
    # Получаем активные бочки
    barrels = get_active_barrels(db, warehouse_id, semi_product_id)
    
    if not barrels:
        raise ValueError(f"Нет активных бочек с полуфабрикатом ID={semi_product_id}")
    
    # Считаем общий доступный вес
    total_available = sum(b.current_weight for b in barrels)
    
    if total_available < required_weight:
        raise ValueError(
            f"Недостаточно полуфабриката: требуется {required_weight} кг, "
            f"доступно {total_available} кг в {len(barrels)} бочках"
        )
    
    # Выбираем бочки по FIFO до покрытия требуемого веса
    selected_barrels = []
    accumulated_weight = 0.0
    
    for barrel in barrels:
        selected_barrels.append(barrel)
        accumulated_weight += barrel.current_weight
        
        if accumulated_weight >= required_weight:
            break
    
    logger.info(
        f"Выбрано {len(selected_barrels)} бочек по FIFO, "
        f"общий вес={accumulated_weight:.2f} кг"
    )
    
    return selected_barrels, accumulated_weight


def calculate_barrel_distribution(
    barrels: List[Barrel],
    required_weight: float
) -> List[Dict]:
    """
    Расчет распределения веса по бочкам (FIFO).
    
    Args:
        barrels: Список бочек (отсортирован по FIFO)
        required_weight: Требуемый вес (кг)
        
    Returns:
        List[Dict]: [{barrel_id, weight_to_use, will_be_empty}, ...]
        
    Example:
        >>> distribution = calculate_barrel_distribution(barrels, 100.0)
        >>> for item in distribution:
        ...     print(f"Бочка {item['barrel_id']}: использовать {item['weight_to_use']} кг")
    """
    from app.utils.calculations import calculate_fifo_distribution
    
    # Подготавливаем данные для расчета
    barrel_data = [
        {
            'id': b.id,
            'current_weight': b.current_weight,
            'created_at': b.created_at
        }
        for b in barrels
    ]
    
    # Выполняем FIFO-распределение
    distribution = calculate_fifo_distribution(barrel_data, required_weight)
    
    # Дополняем информацией о том, будет ли бочка пуста
    for item in distribution:
        barrel = next(b for b in barrels if b.id == item['barrel_id'])
        item['will_be_empty'] = barrel.current_weight == item['weight_to_use']
        item['remaining_weight'] = barrel.current_weight - item['weight_to_use']
    
    logger.debug(f"Распределение по {len(distribution)} бочкам: {distribution}")
    
    return distribution


# ============================================================================
# ОБНОВЛЕНИЕ ВЕСОВ БОЧЕК
# ============================================================================

def update_barrel_weight(
    db: Session,
    barrel_id: int,
    weight_used: float,
    auto_deactivate: bool = True
) -> Barrel:
    """
    Обновление веса бочки после использования.
    
    Args:
        db: Сессия БД
        barrel_id: ID бочки
        weight_used: Использованный вес (кг)
        auto_deactivate: Автоматически деактивировать если вес = 0
        
    Returns:
        Barrel: Обновленная бочка
        
    Raises:
        ValueError: Если данные невалидны
    """
    barrel = get_barrel_by_id(db, barrel_id, load_relations=False)
    
    if not barrel:
        raise ValueError(f"Бочка ID={barrel_id} не найдена")
    
    if not barrel.is_active:
        raise ValueError(f"Бочка ID={barrel_id} неактивна")
    
    if weight_used <= 0:
        raise ValueError("Использованный вес должен быть положительным")
    
    if weight_used > barrel.current_weight:
        raise ValueError(
            f"Использованный вес ({weight_used} кг) превышает "
            f"текущий вес бочки ({barrel.current_weight} кг)"
        )
    
    old_weight = barrel.current_weight
    barrel.current_weight -= weight_used
    barrel.current_weight = round(barrel.current_weight, 2)
    
    # Автоматическая деактивация если вес стал нулевым или отрицательным
    if auto_deactivate and barrel.current_weight <= 0.01:  # Допуск на округление
        barrel.current_weight = 0
        barrel.is_active = False
        logger.info(f"Бочка ID={barrel_id} опустошена и деактивирована")
    
    db.flush()
    db.refresh(barrel)
    
    logger.debug(
        f"Бочка ID={barrel_id}: вес обновлен {old_weight:.2f} → {barrel.current_weight:.2f} кг "
        f"(использовано {weight_used:.2f} кг)"
    )
    
    return barrel


def deactivate_barrel(
    db: Session,
    barrel_id: int,
    force: bool = False
) -> Barrel:
    """
    Деактивация бочки.
    
    Args:
        db: Сессия БД
        barrel_id: ID бочки
        force: Принудительная деактивация (даже если есть остаток)
        
    Returns:
        Barrel: Обновленная бочка
        
    Raises:
        ValueError: Если бочка не может быть деактивирована
    """
    barrel = get_barrel_by_id(db, barrel_id, load_relations=False)
    
    if not barrel:
        raise ValueError(f"Бочка ID={barrel_id} не найдена")
    
    if not barrel.is_active:
        raise ValueError(f"Бочка ID={barrel_id} уже неактивна")
    
    # Проверка остатка
    if not force and barrel.current_weight > 0.01:
        raise ValueError(
            f"Бочка ID={barrel_id} содержит {barrel.current_weight} кг. "
            "Используйте force=True для принудительной деактивации."
        )
    
    barrel.is_active = False
    barrel.current_weight = 0  # Обнуляем остаток при деактивации
    
    db.flush()
    db.refresh(barrel)
    
    logger.info(f"Бочка ID={barrel_id} деактивирована")
    
    return barrel


def reactivate_barrel(
    db: Session,
    barrel_id: int
) -> Barrel:
    """
    Реактивация бочки (восстановление).
    
    Args:
        db: Сессия БД
        barrel_id: ID бочки
        
    Returns:
        Barrel: Обновленная бочка
        
    Raises:
        ValueError: Если бочка не может быть реактивирована
    """
    barrel = get_barrel_by_id(db, barrel_id, load_relations=False)
    
    if not barrel:
        raise ValueError(f"Бочка ID={barrel_id} не найдена")
    
    if barrel.is_active:
        raise ValueError(f"Бочка ID={barrel_id} уже активна")
    
    if barrel.current_weight <= 0:
        raise ValueError(f"Бочка ID={barrel_id} пуста, реактивация невозможна")
    
    barrel.is_active = True
    
    db.flush()
    db.refresh(barrel)
    
    logger.info(f"Бочка ID={barrel_id} реактивирована")
    
    return barrel


# ============================================================================
# СТАТИСТИКА И ИНФОРМАЦИЯ
# ============================================================================

def get_barrel_balance(
    db: Session,
    barrel_id: int
) -> Dict:
    """
    Получение баланса бочки.
    
    Args:
        db: Сессия БД
        barrel_id: ID бочки
        
    Returns:
        Dict: Информация о балансе
    """
    barrel = get_barrel_by_id(db, barrel_id, load_relations=True)
    
    if not barrel:
        return None
    
    used_weight = barrel.initial_weight - barrel.current_weight
    usage_percent = (used_weight / barrel.initial_weight * 100) if barrel.initial_weight > 0 else 0
    
    return {
        'barrel_id': barrel.id,
        'semi_product_name': barrel.semi_product.name,
        'initial_weight': barrel.initial_weight,
        'current_weight': barrel.current_weight,
        'used_weight': round(used_weight, 2),
        'usage_percent': round(usage_percent, 2),
        'is_active': barrel.is_active,
        'created_at': barrel.created_at
    }


def get_warehouse_barrels_summary(
    db: Session,
    warehouse_id: int,
    semi_product_id: int = None
) -> Dict:
    """
    Сводка по бочкам на складе.
    
    Args:
        db: Сессия БД
        warehouse_id: ID склада
        semi_product_id: Фильтр по полуфабрикату (опционально)
        
    Returns:
        Dict: Сводка
    """
    barrels = get_barrels(db, warehouse_id, semi_product_id, is_active=True)
    
    total_barrels = len(barrels)
    total_weight = sum(b.current_weight for b in barrels)
    
    # Группировка по полуфабрикатам
    by_product = {}
    for barrel in barrels:
        product_id = barrel.semi_product_id
        product_name = barrel.semi_product.name
        
        if product_id not in by_product:
            by_product[product_id] = {
                'product_name': product_name,
                'barrels_count': 0,
                'total_weight': 0
            }
        
        by_product[product_id]['barrels_count'] += 1
        by_product[product_id]['total_weight'] += barrel.current_weight
    
    # Округляем веса
    for product_data in by_product.values():
        product_data['total_weight'] = round(product_data['total_weight'], 2)
    
    summary = {
        'warehouse_id': warehouse_id,
        'total_barrels': total_barrels,
        'total_weight': round(total_weight, 2),
        'by_product': by_product
    }
    
    logger.debug(f"Сводка по бочкам склада {warehouse_id}: {total_barrels} бочек, {total_weight:.2f} кг")
    
    return summary


def get_barrel_usage_history(
    db: Session,
    barrel_id: int
) -> List[Dict]:
    """
    История использования бочки.
    
    Args:
        db: Сессия БД
        barrel_id: ID бочки
        
    Returns:
        List[Dict]: История movements связанных с бочкой
    """
    from app.database.models import Movement, MovementType
    
    query = select(Movement).where(
        Movement.barrel_id == barrel_id
    ).options(
        joinedload(Movement.sku),
        joinedload(Movement.user)
    ).order_by(Movement.created_at)
    
    result = db.execute(query)
    movements = result.scalars().unique().all()
    
    history = [
        {
            'movement_id': m.id,
            'type': m.type.value,
            'quantity': m.quantity,
            'sku_name': m.sku.name,
            'user_id': m.user_id,
            'created_at': m.created_at,
            'notes': m.notes
        }
        for m in movements
    ]
    
    logger.debug(f"История бочки {barrel_id}: {len(history)} записей")
    
    return history


def find_oldest_barrel(
    db: Session,
    semi_product_id: int,
    warehouse_id: int = None,
    min_weight: float = 0.1
) -> Optional[Barrel]:
    """
    Поиск самой старой бочки (FIFO).
    
    Args:
        db: Сессия БД
        semi_product_id: ID полуфабриката
        warehouse_id: ID склада (опционально)
        min_weight: Минимальный вес (кг)
        
    Returns:
        Optional[Barrel]: Самая старая бочка или None
    """
    query = select(Barrel).where(
        and_(
            Barrel.semi_product_id == semi_product_id,
            Barrel.is_active == True,
            Barrel.current_weight >= min_weight
        )
    )
    
    if warehouse_id:
        query = query.where(Barrel.warehouse_id == warehouse_id)
    
    query = query.order_by(Barrel.created_at).limit(1)
    
    result = db.execute(query)
    barrel = result.scalar_one_or_none()
    
    if barrel:
        logger.debug(
            f"Самая старая бочка: ID={barrel.id}, "
            f"вес={barrel.current_weight} кг, дата={barrel.created_at}"
        )
    
    return barrel


def get_empty_barrels(
    db: Session,
    warehouse_id: int = None,
    days: int = 30
) -> List[Barrel]:
    """
    Получение пустых (неактивных) бочек.
    
    Args:
        db: Сессия БД
        warehouse_id: ID склада (опционально)
        days: За сколько дней (опционально)
        
    Returns:
        List[Barrel]: Список пустых бочек
    """
    from datetime import timedelta
    
    query = select(Barrel).where(Barrel.is_active == False)
    
    if warehouse_id:
        query = query.where(Barrel.warehouse_id == warehouse_id)
    
    if days:
        query = query.where(
            Barrel.created_at >= datetime.utcnow() - timedelta(days=days)
        )
    
    query = query.options(joinedload(Barrel.semi_product))
    query = query.order_by(desc(Barrel.created_at))
    
    result = db.execute(query)
    barrels = result.scalars().unique().all()
    
    logger.debug(f"Найдено {len(barrels)} пустых бочек")
    
    return list(barrels)


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def get_barrel_details(
    db: Session,
    barrel_id: int
) -> Dict:
    """
    Получение детальной информации о бочке.
    
    Args:
        db: Сессия БД
        barrel_id: ID бочки
        
    Returns:
        Dict: Словарь с данными бочки
    """
    barrel = get_barrel_by_id(db, barrel_id, load_relations=True)
    
    if not barrel:
        return None
    
    balance = get_barrel_balance(db, barrel_id)
    
    return {
        'id': barrel.id,
        'warehouse_id': barrel.warehouse_id,
        'warehouse_name': barrel.warehouse.name,
        'semi_product_id': barrel.semi_product_id,
        'semi_product_name': barrel.semi_product.name,
        'production_batch_id': barrel.production_batch_id,
        'initial_weight': barrel.initial_weight,
        'current_weight': barrel.current_weight,
        'used_weight': balance['used_weight'],
        'usage_percent': balance['usage_percent'],
        'is_active': barrel.is_active,
        'created_at': barrel.created_at
    }
