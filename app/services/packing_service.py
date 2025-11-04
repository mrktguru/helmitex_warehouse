"""
Сервис для фасовки полуфабрикатов в готовую продукцию.

Основные функции:
- Управление вариантами упаковки
- Расчет максимального количества упаковок
- Выполнение фасовки (FIFO-списание бочек)
- Обновление весов бочек
- Оприходование готовой продукции
- История фасовки
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, desc

from app.database.models import (
    PackingVariant, ContainerType, SKU, SKUType,
    Barrel, Movement, MovementType, Stock
)
from app.services import barrel_service, stock_service
from app.utils.calculations import (
    calculate_max_packing_units,
    calculate_packing_remainder
)
from app.logger import get_logger

logger = get_logger("packing_service")


# ============================================================================
# УПРАВЛЕНИЕ ВАРИАНТАМИ УПАКОВКИ
# ============================================================================

def create_packing_variant(
    db: Session,
    semi_product_id: int,
    finished_product_id: int,
    container_type: ContainerType,
    weight_per_unit: float
) -> PackingVariant:
    """
    Создание варианта упаковки.
    
    Args:
        db: Сессия БД
        semi_product_id: ID полуфабриката (SKU type='semi')
        finished_product_id: ID готовой продукции (SKU type='finished')
        container_type: Тип тары
        weight_per_unit: Вес одной упаковки (кг)
        
    Returns:
        PackingVariant: Созданный вариант упаковки
        
    Raises:
        ValueError: Если данные невалидны
        
    Example:
        >>> variant = create_packing_variant(
        ...     db, semi_product_id=10, finished_product_id=20,
        ...     container_type=ContainerType.bucket, weight_per_unit=10.0
        ... )
    """
    logger.info(
        f"Создание варианта упаковки: полуфабрикат={semi_product_id}, "
        f"готовая продукция={finished_product_id}, вес={weight_per_unit} кг"
    )
    
    # Валидация полуфабриката
    semi_product = db.get(SKU, semi_product_id)
    if not semi_product:
        raise ValueError(f"Полуфабрикат ID={semi_product_id} не найден")
    
    if semi_product.type != SKUType.semi:
        raise ValueError(f"SKU ID={semi_product_id} не является полуфабрикатом")
    
    # Валидация готовой продукции
    finished_product = db.get(SKU, finished_product_id)
    if not finished_product:
        raise ValueError(f"Готовая продукция ID={finished_product_id} не найдена")
    
    if finished_product.type != SKUType.finished:
        raise ValueError(f"SKU ID={finished_product_id} не является готовой продукцией")
    
    # Валидация веса
    if weight_per_unit <= 0:
        raise ValueError("Вес упаковки должен быть положительным")
    
    if weight_per_unit > 9999:
        raise ValueError("Вес упаковки не должен превышать 9999 кг")
    
    # Проверка на дубликат
    existing = db.execute(
        select(PackingVariant).where(
            and_(
                PackingVariant.semi_product_id == semi_product_id,
                PackingVariant.finished_product_id == finished_product_id
            )
        )
    ).scalar_one_or_none()
    
    if existing:
        raise ValueError(
            f"Вариант упаковки для полуфабриката ID={semi_product_id} → "
            f"готовая продукция ID={finished_product_id} уже существует"
        )
    
    # Создаем вариант
    variant = PackingVariant(
        semi_product_id=semi_product_id,
        finished_product_id=finished_product_id,
        container_type=container_type,
        weight_per_unit=weight_per_unit
    )
    
    db.add(variant)
    db.commit()
    db.refresh(variant)
    
    logger.info(f"Вариант упаковки ID={variant.id} создан")
    
    return variant


def get_packing_variant(
    db: Session,
    variant_id: int,
    load_relations: bool = True
) -> Optional[PackingVariant]:
    """
    Получение варианта упаковки по ID.
    
    Args:
        db: Сессия БД
        variant_id: ID варианта
        load_relations: Загружать ли связанные данные
        
    Returns:
        Optional[PackingVariant]: Вариант или None
    """
    query = select(PackingVariant).where(PackingVariant.id == variant_id)
    
    if load_relations:
        query = query.options(
            joinedload(PackingVariant.semi_product),
            joinedload(PackingVariant.finished_product)
        )
    
    result = db.execute(query)
    return result.scalar_one_or_none()


def get_packing_variants(
    db: Session,
    semi_product_id: int = None,
    finished_product_id: int = None
) -> List[PackingVariant]:
    """
    Получение списка вариантов упаковки.
    
    Args:
        db: Сессия БД
        semi_product_id: Фильтр по полуфабрикату (опционально)
        finished_product_id: Фильтр по готовой продукции (опционально)
        
    Returns:
        List[PackingVariant]: Список вариантов
    """
    query = select(PackingVariant)
    
    if semi_product_id:
        query = query.where(PackingVariant.semi_product_id == semi_product_id)
    
    if finished_product_id:
        query = query.where(PackingVariant.finished_product_id == finished_product_id)
    
    query = query.options(
        joinedload(PackingVariant.semi_product),
        joinedload(PackingVariant.finished_product)
    )
    
    result = db.execute(query)
    variants = result.scalars().unique().all()
    
    logger.debug(f"Найдено {len(variants)} вариантов упаковки")
    
    return list(variants)


def get_packing_variants_for_semi_product(
    db: Session,
    semi_product_id: int
) -> List[PackingVariant]:
    """
    Получение всех вариантов упаковки для полуфабриката.
    
    Args:
        db: Сессия БД
        semi_product_id: ID полуфабриката
        
    Returns:
        List[PackingVariant]: Список вариантов
    """
    return get_packing_variants(db, semi_product_id=semi_product_id)


# ============================================================================
# РАСЧЕТЫ ДЛЯ ФАСОВКИ
# ============================================================================

def calculate_available_for_packing(
    db: Session,
    semi_product_id: int,
    warehouse_id: int = None
) -> Tuple[float, int]:
    """
    Расчет доступного количества полуфабриката для фасовки.
    
    Args:
        db: Сессия БД
        semi_product_id: ID полуфабриката
        warehouse_id: ID склада (опционально)
        
    Returns:
        Tuple[float, int]:
            - Общий доступный вес (кг)
            - Количество активных бочек
    """
    # Получаем активные бочки
    barrels = barrel_service.get_active_barrels(db, warehouse_id, semi_product_id)
    
    total_weight = sum(b.current_weight for b in barrels)
    barrels_count = len(barrels)
    
    logger.debug(
        f"Доступно для фасовки: {total_weight:.2f} кг в {barrels_count} бочках "
        f"(полуфабрикат ID={semi_product_id})"
    )
    
    return total_weight, barrels_count


def calculate_max_units(
    db: Session,
    semi_product_id: int,
    weight_per_unit: float,
    warehouse_id: int = None
) -> Dict:
    """
    Расчет максимального количества упаковок.
    
    Args:
        db: Сессия БД
        semi_product_id: ID полуфабриката
        weight_per_unit: Вес одной упаковки (кг)
        warehouse_id: ID склада (опционально)
        
    Returns:
        Dict: Информация о расчете
    """
    # Получаем доступный вес
    total_weight, barrels_count = calculate_available_for_packing(
        db, semi_product_id, warehouse_id
    )
    
    # Рассчитываем максимальное количество
    max_units = calculate_max_packing_units(total_weight, weight_per_unit)
    
    # Рассчитываем остаток
    remainder = calculate_packing_remainder(total_weight, max_units, weight_per_unit)
    
    result = {
        'total_available': total_weight,
        'barrels_count': barrels_count,
        'weight_per_unit': weight_per_unit,
        'max_units': max_units,
        'total_weight_packed': max_units * weight_per_unit,
        'remainder': remainder,
        'remainder_percent': round((remainder / total_weight * 100) if total_weight > 0 else 0, 2)
    }
    
    logger.info(
        f"Расчет фасовки: макс. {max_units} упаковок по {weight_per_unit} кг, "
        f"остаток {remainder:.2f} кг ({result['remainder_percent']}%)"
    )
    
    return result


# ============================================================================
# ВЫПОЛНЕНИЕ ФАСОВКИ
# ============================================================================

def execute_packing(
    db: Session,
    semi_product_id: int,
    finished_product_id: int,
    units_count: int,
    weight_per_unit: float,
    user_id: int,
    warehouse_id: int = None,
    notes: str = None
) -> Dict:
    """
    Выполнение фасовки (основная функция).
    
    Выполняет:
    1. Проверку наличия полуфабриката
    2. FIFO-выборку бочек
    3. Списание полуфабриката из бочек
    4. Обновление весов бочек
    5. Оприходование готовой продукции
    6. Создание movements
    
    Args:
        db: Сессия БД
        semi_product_id: ID полуфабриката
        finished_product_id: ID готовой продукции
        units_count: Количество упаковок (шт)
        weight_per_unit: Вес одной упаковки (кг)
        user_id: ID пользователя
        warehouse_id: ID склада (опционально)
        notes: Примечания (опционально)
        
    Returns:
        Dict: Результат фасовки с детальной информацией
        
    Raises:
        ValueError: Если данные невалидны или недостаточно полуфабриката
        
    Example:
        >>> result = execute_packing(
        ...     db, semi_product_id=10, finished_product_id=20,
        ...     units_count=10, weight_per_unit=10.0, user_id=123
        ... )
        >>> print(f"Упаковано {result['units_packed']} шт")
    """
    logger.info(
        f"Выполнение фасовки: полуфабрикат={semi_product_id}, "
        f"готовая продукция={finished_product_id}, количество={units_count} шт"
    )
    
    # Получаем склад
    if not warehouse_id:
        from app.services import warehouse_service
        warehouse = warehouse_service.get_default_warehouse(db)
        warehouse_id = warehouse.id
    
    # Валидация количества
    if units_count <= 0:
        raise ValueError("Количество упаковок должно быть положительным")
    
    if units_count > 99999:
        raise ValueError("Количество упаковок не должно превышать 99999")
    
    # Рассчитываем требуемый вес
    required_weight = units_count * weight_per_unit
    
    logger.debug(f"Требуется полуфабриката: {required_weight:.2f} кг")
    
    # Проверяем доступность и получаем бочки по FIFO
    try:
        barrels, total_available = barrel_service.get_barrels_fifo(
            db, semi_product_id, required_weight, warehouse_id
        )
    except ValueError as e:
        logger.error(f"Недостаточно полуфабриката: {e}")
        raise
    
    # Рассчитываем распределение по бочкам
    distribution = barrel_service.calculate_barrel_distribution(barrels, required_weight)
    
    logger.debug(f"Распределение по {len(distribution)} бочкам: {distribution}")
    
    # Начинаем транзакцию
    try:
        used_barrels = []
        
        # 1. Списываем из бочек
        for item in distribution:
            barrel_id = item['barrel_id']
            weight_to_use = item['weight_to_use']
            
            # Обновляем вес бочки
            barrel = barrel_service.update_barrel_weight(
                db, barrel_id, weight_to_use, auto_deactivate=True
            )
            
            # Создаем movement (расход полуфабриката из бочки)
            movement = Movement(
                warehouse_id=warehouse_id,
                sku_id=semi_product_id,
                type=MovementType.packing,
                quantity=-weight_to_use,
                user_id=user_id,
                barrel_id=barrel_id,
                notes=notes or f"Фасовка: {units_count} шт × {weight_per_unit} кг"
            )
            db.add(movement)
            
            used_barrels.append({
                'barrel_id': barrel_id,
                'weight_used': weight_to_use,
                'is_empty': item['will_be_empty']
            })
            
            logger.debug(
                f"Бочка ID={barrel_id}: списано {weight_to_use:.2f} кг, "
                f"остаток {item['remaining_weight']:.2f} кг"
            )
        
        # 2. Обновляем остатки полуфабриката на складе
        stock_service.update_stock(db, warehouse_id, semi_product_id, -required_weight)
        
        # 3. Оприходовываем готовую продукцию
        stock_service.update_stock(db, warehouse_id, finished_product_id, units_count)
        
        # Создаем movement (приход готовой продукции)
        movement = Movement(
            warehouse_id=warehouse_id,
            sku_id=finished_product_id,
            type=MovementType.packing,
            quantity=units_count,
            user_id=user_id,
            notes=notes or f"Фасовка из полуфабриката ID={semi_product_id}"
        )
        db.add(movement)
        
        # Коммитим транзакцию
        db.commit()
        
        # Формируем результат
        result = {
            'success': True,
            'semi_product_id': semi_product_id,
            'finished_product_id': finished_product_id,
            'units_packed': units_count,
            'weight_per_unit': weight_per_unit,
            'total_weight_used': required_weight,
            'barrels_used': used_barrels,
            'barrels_count': len(used_barrels),
            'empty_barrels_count': len([b for b in used_barrels if b['is_empty']]),
            'warehouse_id': warehouse_id,
            'user_id': user_id,
            'timestamp': datetime.utcnow()
        }
        
        logger.info(
            f"Фасовка завершена: упаковано {units_count} шт ({required_weight:.2f} кг), "
            f"использовано {len(used_barrels)} бочек"
        )
        
        return result
    
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при выполнении фасовки: {e}", exc_info=True)
        raise


def execute_packing_by_variant(
    db: Session,
    variant_id: int,
    units_count: int,
    user_id: int,
    warehouse_id: int = None,
    notes: str = None
) -> Dict:
    """
    Выполнение фасовки по варианту упаковки.
    
    Args:
        db: Сессия БД
        variant_id: ID варианта упаковки
        units_count: Количество упаковок
        user_id: ID пользователя
        warehouse_id: ID склада (опционально)
        notes: Примечания (опционально)
        
    Returns:
        Dict: Результат фасовки
    """
    # Получаем вариант
    variant = get_packing_variant(db, variant_id, load_relations=True)
    
    if not variant:
        raise ValueError(f"Вариант упаковки ID={variant_id} не найден")
    
    # Выполняем фасовку
    return execute_packing(
        db=db,
        semi_product_id=variant.semi_product_id,
        finished_product_id=variant.finished_product_id,
        units_count=units_count,
        weight_per_unit=variant.weight_per_unit,
        user_id=user_id,
        warehouse_id=warehouse_id,
        notes=notes
    )


# ============================================================================
# ИСТОРИЯ ФАСОВКИ
# ============================================================================

def get_packing_history(
    db: Session,
    user_id: int = None,
    semi_product_id: int = None,
    finished_product_id: int = None,
    limit: int = 50
) -> List[Dict]:
    """
    Получение истории фасовки.
    
    Args:
        db: Сессия БД
        user_id: Фильтр по пользователю (опционально)
        semi_product_id: Фильтр по полуфабрикату (опционально)
        finished_product_id: Фильтр по готовой продукции (опционально)
        limit: Максимальное количество записей
        
    Returns:
        List[Dict]: История фасовки
    """
    query = select(Movement).where(Movement.type == MovementType.packing)
    
    if user_id:
        query = query.where(Movement.user_id == user_id)
    
    if semi_product_id:
        query = query.where(Movement.sku_id == semi_product_id)
    
    if finished_product_id:
        query = query.where(Movement.sku_id == finished_product_id)
    
    query = query.options(
        joinedload(Movement.sku),
        joinedload(Movement.user),
        joinedload(Movement.barrel)
    )
    
    query = query.order_by(desc(Movement.created_at)).limit(limit)
    
    result = db.execute(query)
    movements = result.scalars().unique().all()
    
    # Группируем по операциям фасовки
    # (одна операция = несколько movements: расходы из бочек + приход готовой продукции)
    history = []
    
    for movement in movements:
        if movement.quantity > 0:  # Приход готовой продукции
            history.append({
                'movement_id': movement.id,
                'finished_product_id': movement.sku_id,
                'finished_product_name': movement.sku.name,
                'units_packed': movement.quantity,
                'user_id': movement.user_id,
                'created_at': movement.created_at,
                'notes': movement.notes
            })
    
    logger.debug(f"История фасовки: найдено {len(history)} операций")
    
    return history


def get_packing_statistics(
    db: Session,
    semi_product_id: int = None,
    days: int = 30
) -> Dict:
    """
    Получение статистики фасовки.
    
    Args:
        db: Сессия БД
        semi_product_id: Фильтр по полуфабрикату (опционально)
        days: За сколько дней
        
    Returns:
        Dict: Статистика
    """
    from datetime import timedelta
    from sqlalchemy import func
    
    # Запрос для готовой продукции (приход)
    query = select(
        Movement.sku_id,
        func.count(Movement.id).label('operations_count'),
        func.sum(Movement.quantity).label('total_units')
    ).where(
        and_(
            Movement.type == MovementType.packing,
            Movement.quantity > 0,  # Только приход
            Movement.created_at >= datetime.utcnow() - timedelta(days=days)
        )
    )
    
    if semi_product_id:
        # Нужно найти готовую продукцию, связанную с этим полуфабрикатом
        variants = get_packing_variants(db, semi_product_id=semi_product_id)
        finished_ids = [v.finished_product_id for v in variants]
        
        if finished_ids:
            query = query.where(Movement.sku_id.in_(finished_ids))
    
    query = query.group_by(Movement.sku_id)
    
    result = db.execute(query)
    rows = result.all()
    
    total_operations = sum(row.operations_count for row in rows)
    total_units = sum(row.total_units or 0 for row in rows)
    
    by_product = []
    for row in rows:
        sku = db.get(SKU, row.sku_id)
        by_product.append({
            'finished_product_id': row.sku_id,
            'finished_product_name': sku.name if sku else f"ID={row.sku_id}",
            'operations_count': row.operations_count,
            'total_units': row.total_units
        })
    
    stats = {
        'period_days': days,
        'total_operations': total_operations,
        'total_units_packed': int(total_units),
        'by_product': by_product
    }
    
    logger.debug(f"Статистика фасовки за {days} дней: {total_operations} операций")
    
    return stats


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def validate_packing_request(
    db: Session,
    semi_product_id: int,
    finished_product_id: int,
    units_count: int,
    weight_per_unit: float,
    warehouse_id: int = None
) -> Tuple[bool, str]:
    """
    Валидация запроса на фасовку.
    
    Args:
        db: Сессия БД
        semi_product_id: ID полуфабриката
        finished_product_id: ID готовой продукции
        units_count: Количество упаковок
        weight_per_unit: Вес одной упаковки
        warehouse_id: ID склада (опционально)
        
    Returns:
        Tuple[bool, str]: (валидно, сообщение об ошибке)
    """
    # Проверка полуфабриката
    semi_product = db.get(SKU, semi_product_id)
    if not semi_product:
        return False, f"Полуфабрикат ID={semi_product_id} не найден"
    
    if semi_product.type != SKUType.semi:
        return False, f"SKU '{semi_product.name}' не является полуфабрикатом"
    
    # Проверка готовой продукции
    finished_product = db.get(SKU, finished_product_id)
    if not finished_product:
        return False, f"Готовая продукция ID={finished_product_id} не найдена"
    
    if finished_product.type != SKUType.finished:
        return False, f"SKU '{finished_product.name}' не является готовой продукцией"
    
    # Проверка количества
    if units_count <= 0:
        return False, "Количество упаковок должно быть положительным"
    
    # Проверка веса
    if weight_per_unit <= 0:
        return False, "Вес упаковки должен быть положительным"
    
    # Проверка наличия
    required_weight = units_count * weight_per_unit
    total_available, barrels_count = calculate_available_for_packing(
        db, semi_product_id, warehouse_id
    )
    
    if total_available < required_weight:
        return False, (
            f"Недостаточно полуфабриката: требуется {required_weight:.2f} кг, "
            f"доступно {total_available:.2f} кг"
        )
    
    return True, ""


def get_packing_suggestions(
    db: Session,
    semi_product_id: int,
    warehouse_id: int = None
) -> List[Dict]:
    """
    Получение предложений по фасовке.
    
    Показывает все возможные варианты упаковки с расчетом
    максимального количества.
    
    Args:
        db: Сессия БД
        semi_product_id: ID полуфабриката
        warehouse_id: ID склада (опционально)
        
    Returns:
        List[Dict]: Список предложений
    """
    # Получаем варианты упаковки
    variants = get_packing_variants_for_semi_product(db, semi_product_id)
    
    if not variants:
        return []
    
    # Получаем доступный вес
    total_available, barrels_count = calculate_available_for_packing(
        db, semi_product_id, warehouse_id
    )
    
    suggestions = []
    
    for variant in variants:
        max_info = calculate_max_units(
            db, semi_product_id, variant.weight_per_unit, warehouse_id
        )
        
        suggestions.append({
            'variant_id': variant.id,
            'finished_product_id': variant.finished_product_id,
            'finished_product_name': variant.finished_product.name,
            'container_type': variant.container_type.value,
            'weight_per_unit': variant.weight_per_unit,
            'max_units': max_info['max_units'],
            'total_weight_packed': max_info['total_weight_packed'],
            'remainder': max_info['remainder']
        })
    
    logger.debug(f"Предложения по фасовке: {len(suggestions)} вариантов")
    
    return suggestions
