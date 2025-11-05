"""
Сервис для работы с технологическими картами (рецептами).

Основные функции:
- Создание и управление технологическими картами
- Управление компонентами рецептов
- Расчет потребности сырья по рецепту
- Активация/архивация рецептов
- Валидация рецептов
"""
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_

from app.database.models import (
    TechnologicalCard, RecipeComponent, SKU, SKUType, RecipeStatus
)
from app.utils.calculations import (
    calculate_raw_materials_required,
    validate_percentage_sum
)
from app.logger import get_logger

logger = get_logger("recipe_service")


# ============================================================================
# СОЗДАНИЕ И ПОЛУЧЕНИЕ РЕЦЕПТОВ
# ============================================================================

def create_recipe(
    db: Session,
    name: str,
    semi_product_id: int,
    yield_percent: float,
    components: List[Dict],
    created_by: int,
    description: str = None,
    status: RecipeStatus = RecipeStatus.draft
) -> TechnologicalCard:
    """
    Создание новой технологической карты.
    
    Args:
        db: Сессия БД
        name: Название ТК
        semi_product_id: ID полуфабриката (SKU type='semi')
        yield_percent: Процент выхода (50-100)
        components: Компоненты [{raw_material_id, percentage, order}, ...]
        created_by: ID пользователя-создателя
        description: Описание (опционально)
        status: Статус (по умолчанию draft)
        
    Returns:
        TechnologicalCard: Созданная ТК
        
    Raises:
        ValueError: Если данные невалидны
        
    Example:
        >>> create_recipe(
        ...     db, "Краска белая", semi_product_id=10, yield_percent=85.0,
        ...     components=[
        ...         {'raw_material_id': 1, 'percentage': 45.5, 'order': 1},
        ...         {'raw_material_id': 2, 'percentage': 30.0, 'order': 2},
        ...         {'raw_material_id': 3, 'percentage': 24.5, 'order': 3}
        ...     ],
        ...     created_by=123456789
        ... )
    """
    logger.info(f"Создание ТК '{name}' для полуфабриката ID={semi_product_id}")
    
    # Валидация полуфабриката
    semi_product = db.get(SKU, semi_product_id)
    if not semi_product:
        raise ValueError(f"Полуфабрикат с ID={semi_product_id} не найден")
    
    if semi_product.type != SKUType.semi:
        raise ValueError(f"SKU ID={semi_product_id} не является полуфабрикатом")
    
    # Валидация процента выхода
    if not (50 <= yield_percent <= 100):
        raise ValueError("Процент выхода должен быть от 50 до 100")
    
    # Валидация компонентов
    if not components:
        raise ValueError("Рецепт должен содержать хотя бы один компонент")
    
    # Проверка суммы процентов
    percentages = [c['percentage'] for c in components]
    if not validate_percentage_sum(percentages):
        total = sum(percentages)
        raise ValueError(f"Сумма процентов = {total:.2f}%, должна быть 100%")
    
    # Проверка что все компоненты - сырье
    for component in components:
        raw_material = db.get(SKU, component['raw_material_id'])
        if not raw_material:
            raise ValueError(f"Сырье ID={component['raw_material_id']} не найдено")
        if raw_material.type != SKUType.raw:
            raise ValueError(f"SKU ID={component['raw_material_id']} не является сырьем")
    
    # Создаем ТК
    recipe = TechnologicalCard(
        name=name,
        semi_product_id=semi_product_id,
        yield_percent=yield_percent,
        status=status,
        description=description,
        created_by=created_by
    )
    
    db.add(recipe)
    db.flush()  # Получаем ID рецепта
    
    # Добавляем компоненты
    for component_data in components:
        component = RecipeComponent(
            recipe_id=recipe.id,
            raw_material_id=component_data['raw_material_id'],
            percentage=component_data['percentage'],
            order=component_data.get('order', 0)
        )
        db.add(component)
    
    db.commit()
    db.refresh(recipe)
    
    logger.info(f"ТК ID={recipe.id} '{name}' создана с {len(components)} компонентами")
    
    return recipe


def get_recipe_by_id(
    db: Session,
    recipe_id: int,
    load_components: bool = True
) -> Optional[TechnologicalCard]:
    """
    Получение ТК по ID.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        load_components: Загружать ли компоненты и связанные данные
        
    Returns:
        Optional[TechnologicalCard]: ТК или None
    """
    query = select(TechnologicalCard).where(TechnologicalCard.id == recipe_id)
    
    if load_components:
        query = query.options(
            joinedload(TechnologicalCard.components).joinedload(RecipeComponent.raw_material),
            joinedload(TechnologicalCard.semi_product),
            joinedload(TechnologicalCard.created_by_user)
        )
    
    result = db.execute(query)
    return result.scalar_one_or_none()


def get_recipes(
    db: Session,
    status: RecipeStatus = None,
    semi_product_id: int = None,
    load_components: bool = False
) -> List[TechnologicalCard]:
    """
    Получение списка ТК с фильтрацией.
    
    Args:
        db: Сессия БД
        status: Фильтр по статусу (опционально)
        semi_product_id: Фильтр по полуфабрикату (опционально)
        load_components: Загружать ли компоненты
        
    Returns:
        List[TechnologicalCard]: Список ТК
    """
    query = select(TechnologicalCard)
    
    # Фильтры
    if status:
        query = query.where(TechnologicalCard.status == status)
    
    if semi_product_id:
        query = query.where(TechnologicalCard.semi_product_id == semi_product_id)
    
    # Eager loading
    query = query.options(joinedload(TechnologicalCard.semi_product))
    
    if load_components:
        query = query.options(
            joinedload(TechnologicalCard.components).joinedload(RecipeComponent.raw_material)
        )
    
    query = query.order_by(TechnologicalCard.created_at.desc())
    
    result = db.execute(query)
    recipes = result.scalars().unique().all()
    
    logger.debug(f"Найдено {len(recipes)} ТК (status={status}, semi_product_id={semi_product_id})")
    
    return list(recipes)


def get_active_recipes(
    db: Session,
    semi_product_id: int = None
) -> List[TechnologicalCard]:
    """
    Получение активных ТК.
    
    Args:
        db: Сессия БД
        semi_product_id: Фильтр по полуфабрикату (опционально)
        
    Returns:
        List[TechnologicalCard]: Список активных ТК
    """
    return get_recipes(db, status=RecipeStatus.active, semi_product_id=semi_product_id)


# ============================================================================
# УПРАВЛЕНИЕ СТАТУСОМ РЕЦЕПТОВ
# ============================================================================

def activate_recipe(
    db: Session,
    recipe_id: int
) -> TechnologicalCard:
    """
    Активация ТК (из draft или archived).
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        
    Returns:
        TechnologicalCard: Обновленная ТК
        
    Raises:
        ValueError: Если ТК не найдена или уже активна
    """
    recipe = get_recipe_by_id(db, recipe_id, load_components=False)
    
    if not recipe:
        raise ValueError(f"ТК с ID={recipe_id} не найдена")
    
    if recipe.status == RecipeStatus.active:
        raise ValueError("ТК уже активна")
    
    recipe.status = RecipeStatus.active
    db.commit()
    db.refresh(recipe)
    
    logger.info(f"ТК ID={recipe_id} активирована")
    
    return recipe


def archive_recipe(
    db: Session,
    recipe_id: int
) -> TechnologicalCard:
    """
    Архивация ТК.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        
    Returns:
        TechnologicalCard: Обновленная ТК
        
    Raises:
        ValueError: Если ТК не найдена или уже архивирована
    """
    recipe = get_recipe_by_id(db, recipe_id, load_components=False)
    
    if not recipe:
        raise ValueError(f"ТК с ID={recipe_id} не найдена")
    
    if recipe.status == RecipeStatus.archived:
        raise ValueError("ТК уже архивирована")
    
    recipe.status = RecipeStatus.archived
    db.commit()
    db.refresh(recipe)
    
    logger.info(f"ТК ID={recipe_id} архивирована")
    
    return recipe


def update_recipe_status(
    db: Session,
    recipe_id: int,
    new_status: RecipeStatus
) -> TechnologicalCard:
    """
    Обновление статуса ТК.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        new_status: Новый статус
        
    Returns:
        TechnologicalCard: Обновленная ТК
    """
    recipe = get_recipe_by_id(db, recipe_id, load_components=False)
    
    if not recipe:
        raise ValueError(f"ТК с ID={recipe_id} не найдена")
    
    old_status = recipe.status
    recipe.status = new_status
    db.commit()
    db.refresh(recipe)
    
    logger.info(f"ТК ID={recipe_id}: статус изменен {old_status.value} → {new_status.value}")
    
    return recipe


# ============================================================================
# РЕДАКТИРОВАНИЕ РЕЦЕПТОВ
# ============================================================================

def update_recipe(
    db: Session,
    recipe_id: int,
    name: str = None,
    yield_percent: float = None,
    description: str = None
) -> TechnologicalCard:
    """
    Обновление базовых данных ТК (без компонентов).
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        name: Новое название (опционально)
        yield_percent: Новый процент выхода (опционально)
        description: Новое описание (опционально)
        
    Returns:
        TechnologicalCard: Обновленная ТК
    """
    recipe = get_recipe_by_id(db, recipe_id, load_components=False)
    
    if not recipe:
        raise ValueError(f"ТК с ID={recipe_id} не найдена")
    
    if name:
        recipe.name = name
    
    if yield_percent:
        if not (50 <= yield_percent <= 100):
            raise ValueError("Процент выхода должен быть от 50 до 100")
        recipe.yield_percent = yield_percent
    
    if description is not None:
        recipe.description = description
    
    db.commit()
    db.refresh(recipe)
    
    logger.info(f"ТК ID={recipe_id} обновлена")
    
    return recipe


def update_recipe_components(
    db: Session,
    recipe_id: int,
    components: List[Dict]
) -> TechnologicalCard:
    """
    Обновление компонентов ТК (полная замена).
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        components: Новые компоненты [{raw_material_id, percentage, order}, ...]
        
    Returns:
        TechnologicalCard: Обновленная ТК
        
    Raises:
        ValueError: Если данные невалидны
    """
    recipe = get_recipe_by_id(db, recipe_id, load_components=True)
    
    if not recipe:
        raise ValueError(f"ТК с ID={recipe_id} не найдена")
    
    # Валидация компонентов
    if not components:
        raise ValueError("Рецепт должен содержать хотя бы один компонент")
    
    percentages = [c['percentage'] for c in components]
    if not validate_percentage_sum(percentages):
        total = sum(percentages)
        raise ValueError(f"Сумма процентов = {total:.2f}%, должна быть 100%")
    
    # Удаляем старые компоненты
    for old_component in recipe.components:
        db.delete(old_component)
    
    db.flush()
    
    # Добавляем новые компоненты
    for component_data in components:
        component = RecipeComponent(
            recipe_id=recipe_id,
            raw_material_id=component_data['raw_material_id'],
            percentage=component_data['percentage'],
            order=component_data.get('order', 0)
        )
        db.add(component)
    
    db.commit()
    db.refresh(recipe)
    
    logger.info(f"ТК ID={recipe_id}: компоненты обновлены ({len(components)} шт)")
    
    return recipe


# ============================================================================
# РАСЧЕТЫ ПО РЕЦЕПТАМ
# ============================================================================

def calculate_required_materials(
    db: Session,
    recipe_id: int,
    target_weight: float
) -> Dict[int, float]:
    """
    Расчет потребности сырья по рецепту.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        target_weight: Целевой вес полуфабриката (кг)
        
    Returns:
        Dict[int, float]: {raw_material_id: required_weight}
        
    Raises:
        ValueError: Если ТК не найдена
    """
    recipe = get_recipe_by_id(db, recipe_id, load_components=True)
    
    if not recipe:
        raise ValueError(f"ТК с ID={recipe_id} не найдена")
    
    # Подготавливаем компоненты для расчета
    components = [
        {
            'raw_material_id': c.raw_material_id,
            'percentage': c.percentage
        }
        for c in recipe.components
    ]
    
    # Выполняем расчет
    required = calculate_raw_materials_required(
        target_weight=target_weight,
        yield_percent=recipe.yield_percent,
        components=components
    )
    
    logger.info(f"Расчет по ТК ID={recipe_id}: для {target_weight} кг нужно {len(required)} компонентов")
    
    return required


def get_recipe_details_formatted(
    db: Session,
    recipe_id: int
) -> Dict:
    """
    Получение детальной информации о ТК в удобном формате.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        
    Returns:
        Dict: Словарь с данными ТК
    """
    recipe = get_recipe_by_id(db, recipe_id, load_components=True)
    
    if not recipe:
        return None
    
    components_list = [
        {
            'id': c.id,
            'raw_material_id': c.raw_material_id,
            'raw_material_name': c.raw_material.name,
            'raw_material_category': c.raw_material.category.value if c.raw_material.category else None,
            'percentage': c.percentage,
            'order': c.order
        }
        for c in sorted(recipe.components, key=lambda x: x.order)
    ]
    
    return {
        'id': recipe.id,
        'name': recipe.name,
        'semi_product_id': recipe.semi_product_id,
        'semi_product_name': recipe.semi_product.name,
        'yield_percent': recipe.yield_percent,
        'status': recipe.status.value,
        'description': recipe.description,
        'components': components_list,
        'components_count': len(components_list),
        'created_by': recipe.created_by,
        'created_at': recipe.created_at,
        'updated_at': recipe.updated_at
    }


# ============================================================================
# ВАЛИДАЦИЯ РЕЦЕПТОВ
# ============================================================================

def validate_recipe(
    db: Session,
    recipe_id: int
) -> Tuple[bool, List[str]]:
    """
    Валидация ТК перед активацией.
    
    Проверяет:
    - Наличие компонентов
    - Сумму процентов = 100%
    - Существование всех материалов
    - Корректность типов SKU
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        
    Returns:
        Tuple[bool, List[str]]: (валидна, список ошибок)
    """
    recipe = get_recipe_by_id(db, recipe_id, load_components=True)
    
    if not recipe:
        return False, ["ТК не найдена"]
    
    errors = []
    
    # Проверка наличия компонентов
    if not recipe.components:
        errors.append("ТК не содержит компонентов")
    
    # Проверка полуфабриката
    if recipe.semi_product.type != SKUType.semi:
        errors.append(f"SKU '{recipe.semi_product.name}' не является полуфабрикатом")
    
    # Проверка процента выхода
    if not (50 <= recipe.yield_percent <= 100):
        errors.append(f"Процент выхода {recipe.yield_percent}% вне допустимого диапазона (50-100%)")
    
    # Проверка компонентов
    percentages = []
    for component in recipe.components:
        # Проверка что компонент - сырье
        if component.raw_material.type != SKUType.raw:
            errors.append(f"'{component.raw_material.name}' не является сырьем")
        
        # Проверка процента
        if component.percentage <= 0 or component.percentage > 100:
            errors.append(f"Некорректный процент {component.percentage}% для '{component.raw_material.name}'")
        
        percentages.append(component.percentage)
    
    # Проверка суммы процентов
    if percentages and not validate_percentage_sum(percentages):
        total = sum(percentages)
        errors.append(f"Сумма процентов = {total:.2f}%, должна быть 100%")
    
    is_valid = len(errors) == 0
    
    if is_valid:
        logger.info(f"ТК ID={recipe_id} прошла валидацию")
    else:
        logger.warning(f"ТК ID={recipe_id} не прошла валидацию: {len(errors)} ошибок")
    
    return is_valid, errors


def can_activate_recipe(
    db: Session,
    recipe_id: int
) -> Tuple[bool, str]:
    """
    Проверка возможности активации ТК.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        
    Returns:
        Tuple[bool, str]: (можно активировать, причина отказа)
    """
    recipe = get_recipe_by_id(db, recipe_id, load_components=False)
    
    if not recipe:
        return False, "ТК не найдена"
    
    if recipe.status == RecipeStatus.active:
        return False, "ТК уже активна"
    
    # Валидация
    is_valid, errors = validate_recipe(db, recipe_id)
    
    if not is_valid:
        return False, "; ".join(errors)
    
    return True, ""


# ============================================================================
# УДАЛЕНИЕ РЕЦЕПТОВ
# ============================================================================

def delete_recipe(
    db: Session,
    recipe_id: int,
    force: bool = False
) -> bool:
    """
    Удаление ТК.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        force: Принудительное удаление (даже если есть связанные партии)
        
    Returns:
        bool: True если удалено
        
    Raises:
        ValueError: Если нельзя удалить
    """
    recipe = get_recipe_by_id(db, recipe_id, load_components=False)
    
    if not recipe:
        raise ValueError(f"ТК с ID={recipe_id} не найдена")
    
    # Проверка на использование в партиях производства
    if not force and recipe.production_batches:
        raise ValueError(
            f"ТК используется в {len(recipe.production_batches)} партиях производства. "
            "Используйте архивацию вместо удаления."
        )
    
    db.delete(recipe)
    db.commit()
    
    logger.info(f"ТК ID={recipe_id} удалена")
    
    return True
