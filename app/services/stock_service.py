"""
Сервис для операций со складом (приход, производство, фасовка, отгрузка).
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.database.models import (
    StockMovement, MovementType, Production, Packing, Shipment,
    RawMaterial, SemiProduct, FinishedProduct
)
from app.services import (
    raw_material_service,
    semi_product_service,
    finished_product_service,
    recipe_service
)
from app.exceptions import ValidationError
from app.logger import get_logger

logger = get_logger("stock_service")


# ============================================================================
# ПРИХОД СЫРЬЯ
# ============================================================================

def add_arrival(
    db: Session,
    raw_material_id: int,
    quantity: float,
    operator_id: int,
    notes: Optional[str] = None
) -> StockMovement:
    """
    Оформить приход сырья на склад.
    
    Args:
        db: Сессия БД
        raw_material_id: ID сырья
        quantity: Количество
        operator_id: Telegram ID оператора
        notes: Примечания (опционально)
        
    Returns:
        Запись о движении склада
    """
    if quantity <= 0:
        raise ValidationError("Количество должно быть больше 0")
    
    # Обновляем остаток сырья
    material = raw_material_service.update_stock(db, raw_material_id, quantity)
    
    # Создаем запись о движении
    movement = StockMovement(
        movement_type=MovementType.arrival,
        raw_material_id=raw_material_id,
        quantity=quantity,
        operator_id=operator_id,
        notes=notes
    )
    
    db.add(movement)
    db.commit()
    db.refresh(movement)
    
    logger.info(
        f"Приход сырья: {material.category.name} / {material.name} "
        f"+{quantity} {material.unit.value} (оператор: {operator_id})"
    )
    
    return movement


# ============================================================================
# ПРОИЗВОДСТВО (ЗАМЕС)
# ============================================================================

def start_production(
    db: Session,
    recipe_id: int,
    target_weight: float,
    operator_id: int,
    notes: Optional[str] = None
) -> Production:
    """
    Начать производство полуфабриката по ТК.
    
    Args:
        db: Сессия БД
        recipe_id: ID технологической карты
        target_weight: Целевой вес полуфабриката
        operator_id: Telegram ID оператора
        notes: Примечания (опционально)
        
    Returns:
        Запись о производстве
        
    Raises:
        ValidationError: Если недостаточно сырья
    """
    if target_weight <= 0:
        raise ValidationError("Целевой вес должен быть больше 0")
    
    # Проверяем наличие сырья
    availability = recipe_service.check_materials_availability(db, recipe_id, target_weight)
    
    if not availability["available"]:
        missing = [m for m in availability["materials"] if not m["is_available"]]
        error_msg = "Недостаточно сырья:\n"
        for m in missing:
            error_msg += (
                f"• {m['category']} / {m['name']}: "
                f"требуется {m['required']:.2f} {m['unit']}, "
                f"доступно {m['available_stock']:.2f} {m['unit']}\n"
            )
        raise ValidationError(error_msg)
    
    # Списываем сырье
    materials_needed = recipe_service.calculate_materials_needed(db, recipe_id, target_weight)
    
    for material_id, required_qty in materials_needed.items():
        # Списываем сырье (отрицательное количество)
        raw_material_service.update_stock(db, material_id, -required_qty)
        
        # Создаем запись о списании
        movement = StockMovement(
            movement_type=MovementType.production,
            raw_material_id=material_id,
            quantity=-required_qty,
            operator_id=operator_id,
            notes=f"Производство по ТК ID {recipe_id}"
        )
        db.add(movement)
    
    # Создаем запись о производстве
    production = Production(
        recipe_id=recipe_id,
        target_weight=target_weight,
        actual_weight=target_weight,  # По умолчанию = целевому
        operator_id=operator_id,
        completed_at=datetime.utcnow(),
        notes=notes
    )
    
    db.add(production)
    db.flush()
    
    # Получаем рецепт для определения полуфабриката
    recipe = recipe_service.get_recipe_by_id(db, recipe_id)
    
    # Добавляем полуфабрикат на склад
    semi_product_service.update_stock(db, recipe.semi_product_id, target_weight)
    
    # Создаем запись о поступлении полуфабриката
    movement = StockMovement(
        movement_type=MovementType.production_output,
        semi_product_id=recipe.semi_product_id,
        quantity=target_weight,
        production_id=production.id,
        operator_id=operator_id,
        notes=f"Выход производства по ТК: {recipe.name}"
    )
    db.add(movement)
    
    db.commit()
    db.refresh(production)
    
    logger.info(
        f"Производство завершено: ТК '{recipe.name}', "
        f"получено {target_weight} {recipe.semi_product.unit.value} "
        f"(оператор: {operator_id})"
    )
    
    return production


# ============================================================================
# ФАСОВКА
# ============================================================================

def create_packing(
    db: Session,
    semi_product_id: int,
    finished_product_id: int,
    quantity: int,
    operator_id: int,
    notes: Optional[str] = None
) -> Packing:
    """
    Фасовка полуфабриката в готовую продукцию.
    
    Args:
        db: Сессия БД
        semi_product_id: ID полуфабриката
        finished_product_id: ID готовой продукции
        quantity: Количество упаковок
        operator_id: Telegram ID оператора
        notes: Примечания (опционально)
        
    Returns:
        Запись о фасовке
        
    Raises:
        ValidationError: Если недостаточно полуфабриката
    """
    if quantity <= 0:
        raise ValidationError("Количество упаковок должно быть больше 0")
    
    # Получаем данные о продукции
    finished_product = finished_product_service.get_finished_product_by_id(db, finished_product_id)
    
    # Рассчитываем необходимое количество полуфабриката
    weight_needed = finished_product.package_weight * quantity
    
    # Списываем полуфабрикат
    semi_product_service.update_stock(db, semi_product_id, -weight_needed)
    
    # Создаем запись о списании полуфабриката
    movement = StockMovement(
        movement_type=MovementType.packing,
        semi_product_id=semi_product_id,
        quantity=-weight_needed,
        operator_id=operator_id,
        notes=f"Фасовка в {finished_product.name}"
    )
    db.add(movement)
    
    # Создаем запись о фасовке
    packing = Packing(
        semi_product_id=semi_product_id,
        finished_product_id=finished_product_id,
        quantity=quantity,
        weight_used=weight_needed,
        operator_id=operator_id,
        notes=notes
    )
    
    db.add(packing)
    db.flush()
    
    # Добавляем готовую продукцию на склад
    finished_product_service.update_stock(db, finished_product_id, quantity)
    
    # Создаем запись о поступлении готовой продукции
    movement = StockMovement(
        movement_type=MovementType.packing_output,
        finished_product_id=finished_product_id,
        quantity=quantity,
        packing_id=packing.id,
        operator_id=operator_id,
        notes=f"Фасовка: {quantity} шт"
    )
    db.add(movement)
    
    db.commit()
    db.refresh(packing)
    
    logger.info(
        f"Фасовка завершена: {finished_product.name} "
        f"{quantity} шт ({weight_needed} кг полуфабриката) "
        f"(оператор: {operator_id})"
    )
    
    return packing


# ============================================================================
# ОТГРУЗКА
# ============================================================================

def create_shipment(
    db: Session,
    finished_product_id: int,
    quantity: int,
    operator_id: int,
    destination: Optional[str] = None,
    notes: Optional[str] = None
) -> Shipment:
    """
    Отгрузка готовой продукции.
    
    Args:
        db: Сессия БД
        finished_product_id: ID готовой продукции
        quantity: Количество упаковок
        operator_id: Telegram ID оператора
        destination: Куда отгружено (маркетплейс и т.д.)
        notes: Примечания (опционально)
        
    Returns:
        Запись об отгрузке
        
    Raises:
        ValidationError: Если недостаточно продукции
    """
    if quantity <= 0:
        raise ValidationError("Количество должно быть больше 0")
    
    # Списываем готовую продукцию
    finished_product = finished_product_service.update_stock(db, finished_product_id, -quantity)
    
    # Создаем запись об отгрузке
    shipment = Shipment(
        finished_product_id=finished_product_id,
        quantity=quantity,
        destination=destination,
        operator_id=operator_id,
        notes=notes
    )
    
    db.add(shipment)
    db.flush()
    
    # Создаем запись о движении
    movement = StockMovement(
        movement_type=MovementType.shipment,
        finished_product_id=finished_product_id,
        quantity=-quantity,
        shipment_id=shipment.id,
        operator_id=operator_id,
        notes=f"Отгрузка: {destination or 'не указано'}"
    )
    db.add(movement)
    
    db.commit()
    db.refresh(shipment)
    
    logger.info(
        f"Отгрузка: {finished_product.name} {quantity} шт "
        f"→ {destination or 'не указано'} (оператор: {operator_id})"
    )
    
    return shipment


# ============================================================================
# ИСТОРИЯ ОПЕРАЦИЙ
# ============================================================================

def get_movements(
    db: Session,
    movement_type: Optional[MovementType] = None,
    limit: int = 50
) -> List[StockMovement]:
    """
    Получить историю движений склада.
    
    Args:
        db: Сессия БД
        movement_type: Фильтр по типу операции (опционально)
        limit: Максимальное количество записей
        
    Returns:
        Список движений
    """
    query = select(StockMovement).order_by(desc(StockMovement.created_at)).limit(limit)
    
    if movement_type:
        query = query.where(StockMovement.movement_type == movement_type)
    
    movements = db.execute(query).scalars().all()
    return list(movements)
