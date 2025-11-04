"""
Сервис для управления производством (замес бочек).

Основные функции:
- Создание и управление партиями производства
- Проверка наличия сырья
- Пересчет под доступное сырье
- Выполнение производства (списание сырья, создание бочек)
- История производства
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, desc

from app.database.models import (
    ProductionBatch, ProductionStatus, TechnologicalCard, RecipeStatus,
    Barrel, SKU, SKUType, Stock, Movement, MovementType
)
from app.services import recipe_service, stock_service
from app.utils.calculations import (
    calculate_raw_materials_required,
    calculate_to_available_materials,
    calculate_actual_output_weight,
    validate_stock_availability
)
from app.logger import get_logger

logger = get_logger("production_service")


# ============================================================================
# СОЗДАНИЕ И ПОЛУЧЕНИЕ ПАРТИЙ
# ============================================================================

def create_production_batch(
    db: Session,
    recipe_id: int,
    target_weight: float,
    user_id: int,
    notes: str = None
) -> ProductionBatch:
    """
    Создание партии производства (планирование).
    
    Args:
        db: Сессия БД
        recipe_id: ID технологической карты
        target_weight: Целевой вес полуфабриката (кг)
        user_id: ID пользователя
        notes: Примечания (опционально)
        
    Returns:
        ProductionBatch: Созданная партия
        
    Raises:
        ValueError: Если данные невалидны
        
    Example:
        >>> create_production_batch(db, recipe_id=5, target_weight=150.0, user_id=123)
    """
    logger.info(f"Создание партии производства: ТК ID={recipe_id}, вес={target_weight} кг")
    
    # Проверка ТК
    recipe = recipe_service.get_recipe_by_id(db, recipe_id, load_components=True)
    if not recipe:
        raise ValueError(f"ТК с ID={recipe_id} не найдена")
    
    if recipe.status != RecipeStatus.active:
        raise ValueError(f"ТК '{recipe.name}' не активна (статус: {recipe.status.value})")
    
    # Валидация веса
    if target_weight <= 0:
        raise ValueError("Целевой вес должен быть положительным числом")
    
    if target_weight > 9999:
        raise ValueError("Целевой вес не должен превышать 9999 кг")
    
    # Создаем партию
    batch = ProductionBatch(
        recipe_id=recipe_id,
        target_weight=target_weight,
        user_id=user_id,
        status=ProductionStatus.planned,
        notes=notes
    )
    
    db.add(batch)
    db.commit()
    db.refresh(batch)
    
    logger.info(f"Партия производства ID={batch.id} создана")
    
    return batch


def get_production_batch(
    db: Session,
    batch_id: int,
    load_relations: bool = True
) -> Optional[ProductionBatch]:
    """
    Получение партии производства по ID.
    
    Args:
        db: Сессия БД
        batch_id: ID партии
        load_relations: Загружать ли связанные данные
        
    Returns:
        Optional[ProductionBatch]: Партия или None
    """
    query = select(ProductionBatch).where(ProductionBatch.id == batch_id)
    
    if load_relations:
        query = query.options(
            joinedload(ProductionBatch.recipe).joinedload(TechnologicalCard.components),
            joinedload(ProductionBatch.user),
            joinedload(ProductionBatch.barrels)
        )
    
    result = db.execute(query)
    return result.scalar_one_or_none()


def get_production_history(
    db: Session,
    user_id: int = None,
    status: ProductionStatus = None,
    limit: int = 50
) -> List[ProductionBatch]:
    """
    Получение истории производства.
    
    Args:
        db: Сессия БД
        user_id: Фильтр по пользователю (опционально)
        status: Фильтр по статусу (опционально)
        limit: Максимальное количество записей
        
    Returns:
        List[ProductionBatch]: Список партий
    """
    query = select(ProductionBatch)
    
    if user_id:
        query = query.where(ProductionBatch.user_id == user_id)
    
    if status:
        query = query.where(ProductionBatch.status == status)
    
    query = query.options(
        joinedload(ProductionBatch.recipe),
        joinedload(ProductionBatch.user)
    )
    
    query = query.order_by(desc(ProductionBatch.started_at)).limit(limit)
    
    result = db.execute(query)
    batches = result.scalars().unique().all()
    
    logger.debug(f"История производства: найдено {len(batches)} партий")
    
    return list(batches)


# ============================================================================
# ПРОВЕРКА НАЛИЧИЯ СЫРЬЯ
# ============================================================================

def check_materials_availability(
    db: Session,
    recipe_id: int,
    target_weight: float,
    warehouse_id: int = None
) -> Tuple[bool, Dict[int, Dict], Dict[int, float]]:
    """
    Проверка наличия сырья для производства.
    
    Args:
        db: Сессия БД
        recipe_id: ID технологической карты
        target_weight: Целевой вес (кг)
        warehouse_id: ID склада (опционально, берется по умолчанию)
        
    Returns:
        Tuple[bool, Dict, Dict]:
            - True если всего сырья достаточно
            - Детальная информация {raw_material_id: {required, available, shortage}}
            - Требуемые количества {raw_material_id: quantity}
            
    Example:
        >>> is_available, details, required = check_materials_availability(
        ...     db, recipe_id=5, target_weight=150.0
        ... )
        >>> if not is_available:
        ...     print("Недостает:", details)
    """
    logger.info(f"Проверка наличия сырья для ТК ID={recipe_id}, вес={target_weight} кг")
    
    # Получаем склад
    if not warehouse_id:
        from app.services import warehouse_service
        warehouse = warehouse_service.get_default_warehouse(db)
        if not warehouse:
            raise ValueError("Склад по умолчанию не найден")
        warehouse_id = warehouse.id
    
    # Рассчитываем потребность
    required = recipe_service.calculate_required_materials(db, recipe_id, target_weight)
    
    # Получаем доступные остатки
    available = {}
    for material_id in required.keys():
        stock = stock_service.get_stock(db, warehouse_id, material_id)
        available[material_id] = stock.quantity if stock else 0.0
    
    # Проверяем достаточность
    is_sufficient, shortages = validate_stock_availability(required, available)
    
    # Формируем детальную информацию
    details = {}
    for material_id, req_qty in required.items():
        avail_qty = available[material_id]
        shortage = max(0, req_qty - avail_qty)
        
        # Получаем информацию о материале
        material = db.get(SKU, material_id)
        
        details[material_id] = {
            'material_name': material.name if material else f"ID={material_id}",
            'material_category': material.category.value if material and material.category else None,
            'unit': material.unit.value if material else 'кг',
            'required': req_qty,
            'available': avail_qty,
            'shortage': shortage,
            'is_sufficient': avail_qty >= req_qty
        }
    
    if is_sufficient:
        logger.info("Всего сырья достаточно")
    else:
        shortage_count = len([d for d in details.values() if not d['is_sufficient']])
        logger.warning(f"Недостает {shortage_count} материалов")
    
    return is_sufficient, details, required


def recalculate_to_available(
    db: Session,
    recipe_id: int,
    warehouse_id: int = None
) -> Tuple[float, Dict[int, float], float]:
    """
    Пересчет производства под доступное сырье.
    
    Находит максимальный вес, который можно произвести
    из доступного сырья.
    
    Args:
        db: Сессия БД
        recipe_id: ID технологической карты
        warehouse_id: ID склада (опционально)
        
    Returns:
        Tuple[float, Dict[int, float], float]:
            - Максимальный вес выхода (кг)
            - Требуемые количества {raw_material_id: quantity}
            - Коэффициент уменьшения (0-1)
            
    Example:
        >>> max_weight, required, ratio = recalculate_to_available(db, recipe_id=5)
        >>> print(f"Можно произвести: {max_weight} кг (коэффициент {ratio*100}%)")
    """
    logger.info(f"Пересчет под доступное сырье для ТК ID={recipe_id}")
    
    # Получаем рецепт
    recipe = recipe_service.get_recipe_by_id(db, recipe_id, load_components=True)
    if not recipe:
        raise ValueError(f"ТК с ID={recipe_id} не найдена")
    
    # Получаем склад
    if not warehouse_id:
        from app.services import warehouse_service
        warehouse = warehouse_service.get_default_warehouse(db)
        warehouse_id = warehouse.id
    
    # Начинаем с некоторого большого значения и уменьшаем
    # Можно использовать более умный алгоритм, но для простоты:
    # Берем большой вес (например 1000 кг) и смотрим что ограничивает
    
    test_weight = 1000.0
    required_for_test = recipe_service.calculate_required_materials(db, recipe_id, test_weight)
    
    # Получаем доступные остатки
    available = {}
    for material_id in required_for_test.keys():
        stock = stock_service.get_stock(db, warehouse_id, material_id)
        available[material_id] = stock.quantity if stock else 0.0
    
    # Пересчитываем под доступное
    recalculated, ratio = calculate_to_available_materials(required_for_test, available)
    
    # Рассчитываем максимальный вес выхода
    max_output_weight = test_weight * ratio
    
    logger.info(
        f"Максимальный вес: {max_output_weight:.2f} кг "
        f"(коэффициент {ratio*100:.1f}%)"
    )
    
    return max_output_weight, recalculated, ratio


# ============================================================================
# ВЫПОЛНЕНИЕ ПРОИЗВОДСТВА
# ============================================================================

def execute_production(
    db: Session,
    batch_id: int,
    actual_weight: float,
    warehouse_id: int = None
) -> Tuple[ProductionBatch, Barrel]:
    """
    Выполнение производства (основная функция).
    
    Выполняет:
    1. Проверку наличия сырья
    2. Списание сырья со склада (FIFO)
    3. Создание бочки с полуфабрикатом
    4. Оприходование полуфабриката
    5. Создание movements для всех операций
    6. Обновление статуса партии
    
    Args:
        db: Сессия БД
        batch_id: ID партии производства
        actual_weight: Фактический вес готового полуфабриката (кг)
        warehouse_id: ID склада (опционально)
        
    Returns:
        Tuple[ProductionBatch, Barrel]: Обновленная партия и созданная бочка
        
    Raises:
        ValueError: Если данные невалидны или недостаточно сырья
        
    Example:
        >>> batch, barrel = execute_production(db, batch_id=10, actual_weight=148.5)
        >>> print(f"Бочка ID={barrel.id} создана, вес={barrel.initial_weight} кг")
    """
    logger.info(f"Выполнение производства: партия ID={batch_id}, фактический вес={actual_weight} кг")
    
    # Получаем партию
    batch = get_production_batch(db, batch_id, load_relations=True)
    if not batch:
        raise ValueError(f"Партия ID={batch_id} не найдена")
    
    if batch.status == ProductionStatus.completed:
        raise ValueError("Партия уже завершена")
    
    if batch.status == ProductionStatus.cancelled:
        raise ValueError("Партия отменена")
    
    # Получаем склад
    if not warehouse_id:
        from app.services import warehouse_service
        warehouse = warehouse_service.get_default_warehouse(db)
        warehouse_id = warehouse.id
    
    # Валидация фактического веса
    if actual_weight <= 0:
        raise ValueError("Фактический вес должен быть положительным")
    
    # Рассчитываем потребность сырья (на основе целевого веса)
    required = recipe_service.calculate_required_materials(
        db, batch.recipe_id, batch.target_weight
    )
    
    # Проверяем наличие
    is_available, details, _ = check_materials_availability(
        db, batch.recipe_id, batch.target_weight, warehouse_id
    )
    
    if not is_available:
        shortage_list = [
            f"{d['material_name']}: недостает {d['shortage']} {d['unit']}"
            for d in details.values() if not d['is_sufficient']
        ]
        raise ValueError(
            f"Недостаточно сырья:\n" + "\n".join(shortage_list)
        )
    
    # Начинаем транзакцию
    try:
        # 1. Обновляем статус партии
        batch.status = ProductionStatus.in_progress
        batch.actual_weight = actual_weight
        db.flush()
        
        # 2. Списываем сырье
        for material_id, req_qty in required.items():
            # Списываем со склада
            stock_service.update_stock(
                db, warehouse_id, material_id, -req_qty
            )
            
            # Создаем movement (расход)
            movement = Movement(
                warehouse_id=warehouse_id,
                sku_id=material_id,
                type=MovementType.production,
                quantity=-req_qty,
                user_id=batch.user_id,
                production_batch_id=batch.id,
                notes=f"Производство партии #{batch.id}"
            )
            db.add(movement)
            
            logger.debug(f"Списано сырье SKU ID={material_id}: {req_qty} кг")
        
        # 3. Создаем бочку с полуфабрикатом
        from app.services import barrel_service
        barrel = barrel_service.create_barrel(
            db=db,
            warehouse_id=warehouse_id,
            semi_product_id=batch.recipe.semi_product_id,
            production_batch_id=batch.id,
            initial_weight=actual_weight
        )
        
        logger.info(f"Бочка ID={barrel.id} создана, вес={actual_weight} кг")
        
        # 4. Оприходовываем полуфабрикат
        stock_service.update_stock(
            db, warehouse_id, batch.recipe.semi_product_id, actual_weight
        )
        
        # Создаем movement (приход полуфабриката)
        movement = Movement(
            warehouse_id=warehouse_id,
            sku_id=batch.recipe.semi_product_id,
            type=MovementType.production,
            quantity=actual_weight,
            user_id=batch.user_id,
            production_batch_id=batch.id,
            barrel_id=barrel.id,
            notes=f"Производство партии #{batch.id}, бочка #{barrel.id}"
        )
        db.add(movement)
        
        logger.debug(f"Оприходован полуфабрикат SKU ID={batch.recipe.semi_product_id}: {actual_weight} кг")
        
        # 5. Завершаем партию
        batch.status = ProductionStatus.completed
        batch.completed_at = datetime.utcnow()
        
        # Коммитим транзакцию
        db.commit()
        db.refresh(batch)
        db.refresh(barrel)
        
        logger.info(
            f"Производство завершено: партия ID={batch.id}, "
            f"бочка ID={barrel.id}, вес={actual_weight} кг"
        )
        
        return batch, barrel
    
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при выполнении производства: {e}", exc_info=True)
        
        # Возвращаем партию в статус planned
        batch.status = ProductionStatus.planned
        db.commit()
        
        raise


def cancel_production_batch(
    db: Session,
    batch_id: int,
    reason: str = None
) -> ProductionBatch:
    """
    Отмена партии производства.
    
    Args:
        db: Сессия БД
        batch_id: ID партии
        reason: Причина отмены (опционально)
        
    Returns:
        ProductionBatch: Обновленная партия
        
    Raises:
        ValueError: Если партия уже завершена
    """
    batch = get_production_batch(db, batch_id, load_relations=False)
    
    if not batch:
        raise ValueError(f"Партия ID={batch_id} не найдена")
    
    if batch.status == ProductionStatus.completed:
        raise ValueError("Нельзя отменить завершенную партию")
    
    batch.status = ProductionStatus.cancelled
    if reason:
        batch.notes = f"{batch.notes or ''}\nОтменена: {reason}".strip()
    
    db.commit()
    db.refresh(batch)
    
    logger.info(f"Партия ID={batch_id} отменена")
    
    return batch


# ============================================================================
# СТАТИСТИКА И АНАЛИТИКА
# ============================================================================

def get_production_statistics(
    db: Session,
    recipe_id: int = None,
    days: int = 30
) -> Dict:
    """
    Получение статистики производства.
    
    Args:
        db: Сессия БД
        recipe_id: Фильтр по ТК (опционально)
        days: За сколько дней (по умолчанию 30)
        
    Returns:
        Dict: Статистика
    """
    from datetime import timedelta
    
    query = select(ProductionBatch).where(
        ProductionBatch.started_at >= datetime.utcnow() - timedelta(days=days)
    )
    
    if recipe_id:
        query = query.where(ProductionBatch.recipe_id == recipe_id)
    
    result = db.execute(query)
    batches = result.scalars().all()
    
    completed_batches = [b for b in batches if b.status == ProductionStatus.completed]
    
    total_batches = len(batches)
    completed_count = len(completed_batches)
    cancelled_count = len([b for b in batches if b.status == ProductionStatus.cancelled])
    
    total_target_weight = sum(b.target_weight for b in completed_batches)
    total_actual_weight = sum(b.actual_weight or 0 for b in completed_batches)
    
    avg_yield = 0
    if total_target_weight > 0:
        avg_yield = (total_actual_weight / total_target_weight) * 100
    
    stats = {
        'period_days': days,
        'total_batches': total_batches,
        'completed': completed_count,
        'cancelled': cancelled_count,
        'in_progress': total_batches - completed_count - cancelled_count,
        'total_target_weight': round(total_target_weight, 2),
        'total_actual_weight': round(total_actual_weight, 2),
        'average_yield_percent': round(avg_yield, 2),
        'completion_rate': round((completed_count / total_batches * 100) if total_batches > 0 else 0, 2)
    }
    
    logger.debug(f"Статистика производства за {days} дней: {stats}")
    
    return stats


def get_recipe_usage_frequency(
    db: Session,
    days: int = 30,
    limit: int = 10
) -> List[Dict]:
    """
    Получение частоты использования ТК.
    
    Args:
        db: Сессия БД
        days: За сколько дней
        limit: Максимальное количество записей
        
    Returns:
        List[Dict]: Список ТК с частотой использования
    """
    from datetime import timedelta
    from sqlalchemy import func
    
    query = select(
        TechnologicalCard.id,
        TechnologicalCard.name,
        func.count(ProductionBatch.id).label('usage_count'),
        func.sum(ProductionBatch.actual_weight).label('total_weight')
    ).join(
        ProductionBatch, TechnologicalCard.id == ProductionBatch.recipe_id
    ).where(
        and_(
            ProductionBatch.started_at >= datetime.utcnow() - timedelta(days=days),
            ProductionBatch.status == ProductionStatus.completed
        )
    ).group_by(
        TechnologicalCard.id, TechnologicalCard.name
    ).order_by(
        desc('usage_count')
    ).limit(limit)
    
    result = db.execute(query)
    rows = result.all()
    
    usage_list = [
        {
            'recipe_id': row.id,
            'recipe_name': row.name,
            'usage_count': row.usage_count,
            'total_weight': round(row.total_weight or 0, 2)
        }
        for row in rows
    ]
    
    logger.debug(f"Частота использования ТК за {days} дней: {len(usage_list)} записей")
    
    return usage_list


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def get_production_batch_details(
    db: Session,
    batch_id: int
) -> Dict:
    """
    Получение детальной информации о партии.
    
    Args:
        db: Сессия БД
        batch_id: ID партии
        
    Returns:
        Dict: Словарь с данными партии
    """
    batch = get_production_batch(db, batch_id, load_relations=True)
    
    if not batch:
        return None
    
    # Информация о рецепте
    recipe_info = {
        'id': batch.recipe.id,
        'name': batch.recipe.name,
        'yield_percent': batch.recipe.yield_percent,
        'semi_product_name': batch.recipe.semi_product.name
    }
    
    # Информация о бочках
    barrels_info = [
        {
            'id': barrel.id,
            'initial_weight': barrel.initial_weight,
            'current_weight': barrel.current_weight,
            'is_active': barrel.is_active
        }
        for barrel in batch.barrels
    ]
    
    return {
        'id': batch.id,
        'recipe': recipe_info,
        'target_weight': batch.target_weight,
        'actual_weight': batch.actual_weight,
        'status': batch.status.value,
        'user_id': batch.user_id,
        'notes': batch.notes,
        'started_at': batch.started_at,
        'completed_at': batch.completed_at,
        'barrels': barrels_info,
        'barrels_count': len(barrels_info)
    }
